"""
Common base classes and utilities for anonymization operations.

This module provides shared functionality for different types of anonymization
operations, including standalone data anonymization and user anonymization.
"""

import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Set
from abc import ABC, abstractmethod
from app import app, db
from app.models.anonymized import IdMapping

logger = logging.getLogger(__name__)

DEFAULT_YEARS = app.config["ANONYMIZATION_THRESHOLD_YEAR"]
DEFAULT_MONTHS = app.config["ANONYMIZATION_THRESHOLD_MONTH"]


class AnonymizationManager:
    """
    Base class for anonymization operations.

    This class provides common functionality for different types of anonymization
    operations, including standalone data anonymization and user anonymization.
    """

    def __init__(
        self,
        operation_type: str,
        verbose: bool = False,
        dry_run: bool = True,
        test_mode: bool = False,
        force_clean: bool = False,
        years: int = DEFAULT_YEARS,
        months: int = DEFAULT_MONTHS,
    ):
        """
        Initialize the anonymization manager.

        Args:
            operation_type: Type of anonymization operation (e.g., "user", "standalone")
            verbose: Enable verbose logging
            dry_run: Perform a dry run without making actual changes
            test_mode: Run in test mode (roll back changes at the end)
            force_clean: Force cleaning of mapping tables
            years: Years threshold for data retention
            months: Months threshold for data retention
        """
        self.operation_type = operation_type
        self.dry_run = dry_run
        self.test_mode = test_mode
        self.force_clean = force_clean
        self.years = years
        self.months = months

        if verbose:
            logger.setLevel(logging.DEBUG)

    def calculate_cutoff_date(self) -> datetime:
        """Calculate the cutoff date based on the configured retention period."""
        return datetime.now() - relativedelta(
            years=self.years, months=self.months
        )

    def log_operation_start(
        self, cutoff_date: datetime, operation_name: str
    ) -> None:
        """
        Log information about the operation being started.

        Args:
            cutoff_date: Date before which data will be processed
            operation_name: Name of the operation (e.g., "verification", "anonymization")
        """
        log_prefix = ""

        if self.test_mode:
            log_prefix = "Test mode: "

        if self.dry_run:
            log_prefix += "Dry run: "

        threshold_info = f"{self.years} years"
        if self.months > 0:
            threshold_info += f" and {self.months} months"

        logger.info(
            f"{log_prefix}Starting {self.operation_type} {operation_name} process "
            f"with cut-off date: {cutoff_date.date()} (threshold: {threshold_info})"
        )

    def handle_tables_cleaning(
        self, should_have_mappings: bool = False
    ) -> bool:
        """
        Handle the cleaning of mapping tables based on mode and parameters.

        Args:
            should_have_mappings: Whether mappings should exist for the operation

        Returns:
            bool: Whether to proceed with the operation
        """
        mapping_count = IdMapping.query.count()

        if should_have_mappings and mapping_count == 0:
            logger.error(
                f"Cannot proceed: No existing mappings found for {self.operation_type} operation"
            )
            return False

        should_clean_initial = (
            not should_have_mappings
            and mapping_count > 0
            and not self.test_mode
        )

        if should_clean_initial and not self.force_clean:
            logger.error(
                f"There are {mapping_count} existing mappings in IdMapping table. "
                f"Use --force-clean to proceed and clean existing mappings."
            )
            return False

        if should_clean_initial and self.force_clean:
            logger.info(
                f"Cleaning {mapping_count} existing mappings from IdMapping table"
            )
            if not self.dry_run:
                self.clean_id_mapping()

        return True

    def handle_final_cleanup(
        self, should_preserve_mappings: bool = False
    ) -> None:
        """
        Handle final cleanup of the mapping table based on the execution mode.

        Args:
            should_preserve_mappings: Whether to preserve mappings for future operations
        """
        if (
            self.dry_run
            and not should_preserve_mappings
            and not self.test_mode
        ):
            mapping_count = IdMapping.query.count()
            logger.info(
                f"Dry run complete: preserving {mapping_count} mappings in IdMapping table. "
                f"Run again without the --dry-run flag to perform actual changes."
            )
            return

        if should_preserve_mappings and self.test_mode:
            mapping_count = IdMapping.query.count()
            logger.info(
                f"Test mode complete: preserving {mapping_count} mappings in IdMapping table "
                f"for future test runs."
            )
            return

        if self.test_mode or (
            not self.dry_run and not should_preserve_mappings
        ):
            clean_reason = self.get_clean_reason()
            logger.info(f"{clean_reason}: cleaning IdMapping table")
            self.clean_id_mapping()

    def get_clean_reason(self) -> str:
        """
        Get the reason for cleaning the mapping table.

        Returns:
            str: The reason for cleaning
        """
        if self.test_mode:
            return "Test mode"

        if not self.dry_run:
            return f"{self.operation_type.capitalize()} operation complete"

        return "Cleanup"

    def handle_exception(
        self, exception: Exception, preserve_mappings: bool = False
    ) -> None:
        """
        Handle exceptions during the anonymization process.

        Args:
            exception: The exception that occurred
            preserve_mappings: Whether to preserve mappings on error
        """
        if self.test_mode and not preserve_mappings:
            logger.info(
                f"Error occurred during test mode: cleaning IdMapping table"
            )
            self.clean_id_mapping()

        if self.test_mode and preserve_mappings:
            logger.info(
                f"Error occurred during test mode: preserving IdMapping table for future test runs"
            )

        if not self.test_mode:
            logger.warning("Error occurred but IdMapping table is preserved")

        logger.error(f"Error details: {str(exception)}")

    @staticmethod
    def clean_id_mapping() -> None:
        """
        Clean the temporary ID mapping table by deleting all entries.
        """
        try:
            IdMapping.query.delete()
            db.session.commit()
            logger.info("IdMapping table cleaned successfully")
        except Exception as e:
            logger.error(f"Error cleaning IdMapping table: {e}")
            db.session.rollback()
            raise

    @abstractmethod
    def execute(self) -> None:
        """
        Execute the anonymization process.

        This is an abstract method that should be implemented by subclasses.
        """
        pass


def log_classification_results(
    full_anonymization: Set[int],
    partial_anonymization: Set[int],
    controller_anonymization: Set[int],
) -> None:
    """
    Log the results of user classification.

    Args:
        full_anonymization: Set of user IDs for full anonymization
        partial_anonymization: Set of user IDs for partial anonymization
        controller_anonymization: Set of controller IDs for anonymization
    """
    logger.info(f"Users for full anonymization: {len(full_anonymization)}")
    logger.info(
        f"Users for partial anonymization: {len(partial_anonymization)}"
    )
    logger.info(
        f"Controllers for anonymization: {len(controller_anonymization)}"
    )
