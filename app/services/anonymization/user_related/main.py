"""
User anonymization module.

This module provides functionality for anonymizing user data that has been
inactive for a specified period, ensuring compliance with data protection
regulations.

Unlike standalone data anonymization, user anonymization modifies user references
in the database rather than migrating and deleting data.
"""

import logging
from typing import Set, Dict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from app import app, db

from app.models.anonymized import IdMapping
from app.services.anonymization.user_related.classifier import UserClassifier
from app.services.anonymization.user_related.user_anonymizer import (
    UserAnonymizer,
)
from app.services.anonymization.common import AnonymizationManager

logger = logging.getLogger(__name__)


class UserAnonymizationManager(AnonymizationManager):
    """
    Manager for user anonymization operations.

    This class coordinates the full process of identifying and anonymizing
    inactive users according to the specified operation mode.

    Unlike the standalone data anonymizer, this class:
    - Modifies user records in place rather than copying them to anonymized tables
    - Sets user status to ANONYMIZED
    - Assigns negative IDs to users (via database sequence)
    - Removes or obfuscates personal information
    - Preserves references and doesn't delete the original records
    """

    def __init__(
        self,
        verbose: bool = False,
        dry_run: bool = True,
        test_mode: bool = False,
        force_clean: bool = False,
    ):
        """
        Initialize the user anonymization manager.

        Args:
            verbose: Enable verbose logging
            dry_run: Perform a dry run without making actual changes
            test_mode: Run in test mode (roll back changes at the end)
            force_clean: Force cleaning of mapping tables
        """
        super().__init__(
            operation_type="user",
            verbose=verbose,
            dry_run=dry_run,
            test_mode=test_mode,
            force_clean=force_clean,
        )

    def process_user_data(self, cutoff_date) -> None:
        """
        Process user data for anonymization.

        Args:
            cutoff_date: Date before which users will be considered for anonymization
        """
        logger.info("Processing user data")

        logger.info("Starting user classification phase")
        classifier = UserClassifier(cutoff_date)
        classification = classifier.find_inactive_users()

        users_to_anon = classification["users"]
        admin_to_anon = classification["admins"]
        controller_to_anon = classification["controllers"]

        user_anonymizer = UserAnonymizer(db.session, dry_run=self.dry_run)

        user_anonymizer.anonymize_user_data(
            users_to_anon,
            admin_to_anon,
            controller_to_anon,
            self.test_mode,
        )

    def execute(self) -> None:
        """
        Execute the user anonymization process.

        This method orchestrates the entire anonymization process:
        1. Validates parameters
        2. Calculates cutoff date
        3. Handles initialization (cleaning tables if needed)
        4. Processes user data for anonymization
        5. Handles final cleanup
        """
        if not self.validate_parameters():
            return

        try:
            cutoff_date = self.calculate_cutoff_date()

            self.log_operation_start(cutoff_date, "anonymization")

            if not self.handle_tables_cleaning():
                return

            self.process_user_data(cutoff_date)

            self.handle_final_cleanup()

            logger.info("User anonymization completed successfully")

            if self.dry_run and not self.test_mode:
                logger.info(
                    "Dry run completed: ID mappings created but no users were modified. "
                    "To perform actual anonymization, run again with --no-dry-run flag."
                )

        except Exception as e:
            self.handle_exception(e)
            raise


def anonymize_users(
    verbose: bool = False,
    dry_run: bool = True,
    test_mode: bool = False,
    force_clean: bool = False,
) -> None:
    """
    Anonymize user data that has been inactive for a specified period.

    - Modifies user records in place rather than copying them to anonymized tables
    - Sets user status to ANONYMIZED
    - Assigns negative IDs to users (via database sequence)
    - Removes or obfuscates personal information
    - Preserves references and doesn't delete the original records

    Args:
        verbose: Enable verbose mode for more detailed logs
        dry_run: Dry-run mode - create ID mappings without modifying users (default: True)
        test_mode: Test mode - roll back all changes at the end
        force_clean: Clean mapping table before starting

    Workflow for effective anonymization:
    1. Run with dry_run=True to create ID mappings without modifying users
    2. Run with dry_run=False to perform actual anonymization by modifying user records
    """
    manager = UserAnonymizationManager(
        verbose=verbose,
        dry_run=dry_run,
        test_mode=test_mode,
        force_clean=force_clean,
    )

    manager.execute()
