from datetime import datetime
import logging
from dateutil.relativedelta import relativedelta
from app import app, db
from app.models.anonymized import IdMapping
from .standalone import StandaloneAnonymizer
from .user_related import UserClassifier, UserAnonymizer

logger = logging.getLogger(__name__)

years = app.config["ANONYMIZATION_THRESHOLD_YEAR"]
months = app.config["ANONYMIZATION_THRESHOLD_MONTH"]


def anonymize_expired_data(
    verbose: bool = False,
    dry_run: bool = True,
    delete_only: bool = False,
    test_mode: bool = False,
    force_clean: bool = False,
) -> None:
    """
    Main function for anonymizing expired data

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

    Note: Delete-only mode is currently implemented only for standalone data.
    User data delete-only mode is not yet implemented.
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    if not dry_run and delete_only:
        logger.warning(
            "Invalid combination: --delete-only cannot be used with --no-dry-run. "
            "The delete-only mode works with the default dry-run setting."
        )
        return

    if delete_only and not IdMapping.query.count():
        logger.error(
            "Cannot run in delete-only mode: No mappings found in IdMapping table. "
            "Run first in dry-run mode to create the necessary mappings."
        )
        return

    try:
        cutoff_date = datetime.now() - relativedelta(
            years=years, months=months
        )
        log_operation_start(dry_run, delete_only, test_mode, cutoff_date)

        if not handle_tables_cleaning(dry_run, delete_only, force_clean):
            return

        process_standalone_data(dry_run, delete_only, test_mode, cutoff_date)

        process_user_data(dry_run, delete_only, test_mode, cutoff_date)

        handle_final_cleanup(dry_run, delete_only, test_mode)

        operation_name = "deletion" if delete_only else "anonymization"
        logger.info(f"Data {operation_name} completed successfully")

        if dry_run and not delete_only and not test_mode:
            logger.info(
                "Dry run completed. To delete the original data after verification, "
                "run again with --delete-only flag."
            )

    except Exception as e:
        handle_exception(e, test_mode, delete_only)
        raise


def log_operation_start(dry_run, delete_only, test_mode, cutoff_date):
    """
    Log information about the operation being started.

    Args:
        dry_run: If True, running in dry-run mode
        delete_only: If True, running in delete-only mode
        test_mode: If True, running in test mode
        cutoff_date: Date before which data should be processed
    """
    log_prefix = ""

    if test_mode:
        log_prefix = "Test mode: "

    if dry_run:
        log_prefix += "Dry run: "

    operation_name = "deletion" if delete_only else "anonymization"

    threshold_info = f"{years} years"
    if months > 0:
        threshold_info += f" and {months} months"

    logger.info(
        f"{log_prefix}Starting data {operation_name} process with cut-off date: {cutoff_date.date()} (threshold: {threshold_info})"
    )


def handle_tables_cleaning(dry_run, delete_only, force_clean):
    """
    Handle the cleaning of mapping tables based on mode and parameters.

    Args:
        dry_run: If True, running in dry-run mode
        delete_only: If True, running in delete-only mode
        force_clean: If True, force cleaning mapping tables

    Returns:
        bool: Whether to proceed with the operation
    """
    mapping_count = IdMapping.query.count()

    if delete_only and mapping_count == 0:
        logger.error(
            "No mappings found in IdMapping table. Cannot perform delete-only operation."
        )
        return False

    should_clean_initial = (
        not dry_run and not delete_only and mapping_count > 0
    )
    if should_clean_initial and not force_clean:
        logger.error(
            f"There are {mapping_count} existing mappings in IdMapping table. "
            f"Use --force-clean to proceed and clean existing mappings. "
            f"Alternatively, use --delete-only to delete the original data based on these mappings."
        )
        return False

    if force_clean or should_clean_initial:
        logger.info(
            f"Force clean enabled. Cleaning {mapping_count} mappings from IdMapping table..."
        )
        clean_id_mapping()

    return True


def process_standalone_data(dry_run, delete_only, test_mode, cutoff_date):
    """
    Process standalone data either by anonymizing or deleting.

    Args:
        dry_run: If True, running in dry-run mode
        delete_only: If True, running in delete-only mode
        test_mode: If True, running in test mode
        cutoff_date: Date before which data should be processed
    """
    operation_type = "Deleting" if delete_only else "Processing"
    logger.info(f"{operation_type} standalone data")

    standalone_anonymizer = StandaloneAnonymizer(
        db.session, dry_run=dry_run, delete_only=delete_only
    )

    if delete_only:
        standalone_anonymizer.delete_anonymized_data(cutoff_date, test_mode)
        return

    standalone_anonymizer.anonymize_standalone_data(cutoff_date, test_mode)


def process_user_data(dry_run, delete_only, test_mode, cutoff_date):
    """
    Process user data either by anonymizing or deleting.

    Args:
        dry_run: If True, running in dry-run mode
        delete_only: If True, running in delete-only mode
        test_mode: If True, running in test mode
        cutoff_date: Date before which data should be processed
    """
    operation_type = "Deleting" if delete_only else "Processing"
    logger.info(f"{operation_type} user data")

    full_anon_users = set()
    partial_anon_users = set()
    controller_anon_users = set()

    if not delete_only:
        logger.info("Starting user classification phase")
        classifier = UserClassifier(cutoff_date)
        classification = classifier.classify_users_for_anonymization()
        full_anon_users = classification["user_full_anonymization"]
        partial_anon_users = classification["user_partial_anonymization"]
        controller_anon_users = classification["controller_user_anonymization"]

        if test_mode:
            log_classification_results(
                full_anon_users, partial_anon_users, controller_anon_users
            )

        logger.info("Getting previously anonymized users from mappings")

    user_anonymizer = UserAnonymizer(db.session, dry_run=dry_run)

    if delete_only:
        logger.warning("Delete-only mode not yet implemented for user data")
        return

    user_anonymizer.anonymize_user_data(
        full_anon_users,
        partial_anon_users,
        controller_anon_users,
        test_mode,
    )


def log_classification_results(
    full_anon_users, partial_anon_users, controller_anon_users
):
    logger.debug("Detailed classification results:")
    logger.debug(
        f"Users ready for full anonymization: {list(full_anon_users)}"
    )
    logger.debug(
        f"Users requiring partial anonymization: {list(partial_anon_users)}"
    )
    logger.debug(
        f"Controller users requiring anonymization: {list(controller_anon_users)}"
    )


def handle_final_cleanup(dry_run, delete_only, test_mode):
    """
    Handle final cleanup of the mapping table based on the execution mode.

    Args:
        dry_run: If True, running in dry-run mode
        delete_only: If True, running in delete-only mode
        test_mode: If True, running in test mode

    Cleanup logic:
    - In regular dry-run: preserve mappings for future delete-only
    - In delete-only: clean mappings after successful deletion
    - In test mode: clean mappings except for delete-only test mode
    - In delete-only test mode: preserve mappings for future test runs
    """
    if dry_run and not delete_only and not test_mode:
        mapping_count = IdMapping.query.count()
        logger.info(
            f"Dry run complete: preserving {mapping_count} mappings in IdMapping table for future deletion. "
            f"Run again with --delete-only to delete the original data."
        )
        return

    if delete_only and test_mode:
        mapping_count = IdMapping.query.count()
        logger.info(
            f"Test mode delete-only complete: preserving {mapping_count} mappings in IdMapping table "
            f"for future test runs."
        )
        return

    clean_reason = get_clean_reason(test_mode, dry_run, delete_only)
    logger.info(f"{clean_reason}: cleaning IdMapping table")
    clean_id_mapping()


def get_clean_reason(test_mode, dry_run, delete_only):
    """
    Get the reason for cleaning the mapping table.

    Args:
        test_mode: If True, running in test mode
        dry_run: If True, running in dry-run mode
        delete_only: If True, running in delete-only mode

    Returns:
        str: The reason for cleaning the mapping table
    """
    if test_mode:
        return "Test mode"

    if not dry_run:
        return "Operation complete"

    if delete_only:
        return "Delete-only operation complete"

    return "Cleanup"


def handle_exception(e, test_mode, delete_only):
    """
    Handle exceptions during the anonymization process.

    Args:
        e: The exception that occurred
        test_mode: If True, running in test mode
        delete_only: If True, running in delete-only mode
    """
    if test_mode and not delete_only:
        logger.info(
            "Error occurred during test mode: cleaning IdMapping table"
        )
        clean_id_mapping()

    if test_mode and delete_only:
        logger.info(
            "Error occurred during delete-only test mode: preserving IdMapping table for future test runs"
        )

    if not test_mode:
        logger.warning("Error occurred but IdMapping table is preserved")

    operation_name = "deletion" if delete_only else "anonymization"
    logger.error(f"Error during {operation_name}: {e}")


def clean_id_mapping():
    """
    Clean the temporary ID mapping table by deleting all entries.

    This function is used to reset the mapping table when:
    1. Starting a new anonymization process with force_clean
    2. Finishing a regular test mode run
    3. Finishing a delete-only operation (after successful deletion)

    Raises:
        Exception: If there is an error during the deletion process
    """
    try:
        IdMapping.query.delete()
        db.session.commit()
        logger.info("IdMapping table cleaned successfully")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error cleaning IdMapping table: {e}")
        raise
