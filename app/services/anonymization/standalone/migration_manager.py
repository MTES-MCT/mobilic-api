"""
Standalone data anonymization module.

This module provides functionality for anonymizing standalone data (like missions,
companies, etc.) that has been inactive for a specified period, ensuring compliance
with data protection regulations.
"""

import logging
from app import db

from app.services.anonymization.common import AnonymizationManager
from app.services.anonymization.standalone.data_finder import DataFinder

logger = logging.getLogger(__name__)


class StandaloneDataAnonymizationManager(AnonymizationManager):
    """
    Manager for standalone data migration and anonymization operations.

    This class coordinates the full process of finding, anonymizing, and optionally
    deleting standalone data (missions, companies, etc.) according to the specified
    operation mode.

    This class handles the anonymization of standalone data, including:
    - Missions, companies, employments, anon_users and their respective dependencies.
    - Executing the anonymization process
    - Optionally deleting original data after anonymization except for anon_users
    """

    def __init__(
        self,
        verbose: bool = False,
        dry_run: bool = True,
        delete_only: bool = False,
        test_mode: bool = False,
        force_clean: bool = False,
    ):
        """
        Initialize the standalone data anonymization manager.

        Args:
            verbose: Enable verbose logging
            dry_run: Perform a dry run without making actual changes
            delete_only: Only delete already anonymized data
            test_mode: Run in test mode (roll back changes at the end)
            force_clean: Force cleaning of mapping tables
        """
        super().__init__(
            operation_type="standalone",
            verbose=verbose,
            dry_run=dry_run,
            test_mode=test_mode,
            force_clean=force_clean,
        )
        self.delete_only = delete_only

        # In delete-only mode, we need to disable dry-run to allow deletions
        if delete_only:
            self.dry_run = False

    def validate_parameters(self) -> bool:
        """
        Validate the input parameters for the anonymization operation.

        Returns:
            bool: Whether the parameters are valid
        """
        return True

    def process_standalone_data(self, cutoff_date) -> None:
        """
        Coordinate standalone data processing based on operation mode.

        This method delegates to the appropriate DataFinder methods depending on whether
        we're in normal mode (anonymize) or delete-only mode (delete originals).

        Args:
            cutoff_date: Date before which data will be processed
        """
        operation_type = "Deleting" if self.delete_only else "Processing"
        logger.info(f"{operation_type} standalone data")

        data_finder = DataFinder(db.session, dry_run=self.dry_run)

        if self.delete_only:
            logger.info("Using delete-only mode for standalone data")
            data_finder.delete_anonymized_data(cutoff_date, self.test_mode)
            return

        data_finder.anonymize_standalone_data(cutoff_date, self.test_mode)

    def execute(self) -> None:
        """
        Execute the standalone data anonymization process.

        This method orchestrates the entire anonymization process:
        1. Validates parameters
        2. Calculates cutoff date
        3. Handles initialization (cleaning tables if needed)
        4. Processes standalone data
        5. Handles final cleanup

        In delete_only mode, it deletes original data that has already been
        anonymized without performing new anonymizations.
        """
        if not self.validate_parameters():
            return

        try:
            cutoff_date = self.calculate_cutoff_date()

            operation_name = (
                "deletion" if self.delete_only else "anonymization"
            )
            self.log_operation_start(cutoff_date, operation_name)

            if not self.handle_tables_cleaning(
                should_have_mappings=self.delete_only
            ):
                return

            self.process_standalone_data(cutoff_date)

            logger.info(
                "Note: User anonymization is handled by the dedicated 'anonymize_users' command. "
                "Use 'flask anonymize_users --help' for more information."
            )

            self.handle_final_cleanup(
                should_preserve_mappings=self.delete_only and self.test_mode
            )

            logger.info(
                f"Standalone data {operation_name} completed successfully"
            )

            if self.dry_run and not self.delete_only and not self.test_mode:
                logger.info(
                    "Dry run completed. To delete the original data after verification, "
                    "run again with --delete-only flag."
                )

        except Exception as e:
            self.handle_exception(
                e, preserve_mappings=self.delete_only and self.test_mode
            )
            raise


def anonymize_expired_data(
    verbose: bool = False,
    dry_run: bool = True,
    delete_only: bool = False,
    test_mode: bool = False,
    force_clean: bool = False,
) -> None:
    """
    Main function for migrating and anonymizing expired standalone data.

    This is the main entry point for standalone data anonymization, creating and executing
    a StandaloneDataAnonymizationManager instance that coordinates the process of copying
    data to anonymized tables and optionally deleting the original records.

    Args:
        verbose: Enable verbose mode for more detailed logs
        dry_run: Dry-run mode - anonymize without deletion (default: True)
        delete_only: Delete-only mode - delete already anonymized data
        test_mode: Test mode - roll back all changes at the end
        force_clean: Clean mapping table before starting

    Workflow for delete-only mode:
    1. Run with dry_run=True to anonymize data and create mappings
    2. Verify the anonymized data is correct
    3. Run with delete_only=True to delete original data using existing mappings

     This allows for verification before permanently deleting original data.

    Note: User anonymization is handled by the dedicated 'anonymize_users' command.
    Use 'flask anonymize_users --help' for more information.
    """
    manager = StandaloneDataAnonymizationManager(
        verbose=verbose,
        dry_run=dry_run,
        delete_only=delete_only,
        test_mode=test_mode,
        force_clean=force_clean,
    )

    manager.execute()
