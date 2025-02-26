from datetime import datetime
import logging
from dateutil.relativedelta import relativedelta
from app import app, db
from app.models.anonymized import IdMapping
from .standalone import StandaloneAnonymizer
from .user_related import UserClassifier, UserAnonymizer

logger = logging.getLogger(__name__)

years = app.config["ANONYMIZATION_THRESHOLD_YEAR"]


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
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    try:
        cutoff_date = datetime.now() - relativedelta(years=years)
        log_operation_start(dry_run, delete_only, test_mode, cutoff_date)

        if not handle_tables_cleaning(dry_run, delete_only, force_clean):
            return

        process_standalone_data(dry_run, delete_only, test_mode, cutoff_date)

        # STEP 2 : User data processing
        # process_user_data(dry_run, delete_only, test_mode, cutoff_date)

        handle_final_cleanup(dry_run, delete_only, test_mode)

        operation_name = "deletion" if delete_only else "anonymization"
        logger.info(f"Data {operation_name} completed successfully")

    except Exception as e:
        handle_exception(e, test_mode, delete_only)
        raise


def log_operation_start(dry_run, delete_only, test_mode, cutoff_date):
    log_prefix = ""
    if test_mode:
        log_prefix = "Test mode: "
    if dry_run:
        log_prefix += "Dry run: "

    operation_name = "deletion" if delete_only else "anonymization"
    logger.info(
        f"{log_prefix}Starting data {operation_name} process with cut-off date: {cutoff_date.date()}"
    )


def handle_tables_cleaning(dry_run, delete_only, force_clean):
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
            f"There are {mapping_count} existing mappings in IdMapping table. Use --force-clean to proceed and clean existing mappings."
        )
        return False

    if force_clean or should_clean_initial:
        logger.info(
            f"Force clean enabled. Cleaning {mapping_count} mappings from IdMapping table..."
        )
        clean_id_mapping()

    return True


def process_standalone_data(dry_run, delete_only, test_mode, cutoff_date):
    operation_type = "Deleting" if delete_only else "Processing"
    logger.info(f"{operation_type} standalone data")

    standalone_anonymizer = StandaloneAnonymizer(db.session, dry_run=dry_run)

    if delete_only:
        # TODO: Implement delete_anonymized_data method in StandaloneAnonymizer
        # standalone_anonymizer.delete_anonymized_data(cutoff_date, test_mode)
        logger.warning(
            "Delete-only mode not yet implemented for standalone data"
        )
    if not delete_only:
        standalone_anonymizer.anonymize_standalone_data(cutoff_date, test_mode)


def process_user_data(dry_run, delete_only, test_mode, cutoff_date):
    operation_type = "Deleting" if delete_only else "Processing"

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
    if not delete_only:
        # STEP 2 :Get users from existing mappings
        logger.info("Getting previously anonymized users from mappings")
        # TODO: Implementation for retrieving users from mappings

    logger.info(f"{operation_type} user data")
    user_anonymizer = UserAnonymizer(db.session, dry_run=dry_run)

    if delete_only:
        # user_anonymizer.delete_anonymized_user_data(
        #     full_anon_users,
        #     partial_anon_users,
        #     controller_anon_users,
        #     test_mode,
        # )
        logger.warning("Delete-only mode not yet implemented for user data")
    if not delete_only:
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
    should_clean_final = test_mode or not dry_run or delete_only

    if should_clean_final:
        clean_reason = get_clean_reason(test_mode, dry_run, delete_only)
        logger.info(f"{clean_reason}: cleaning IdMapping table")
        clean_id_mapping()
    if not should_clean_final:
        logger.info(
            f"Dry run complete: preserving {IdMapping.query.count()} mappings in IdMapping table for future deletion"
        )


def get_clean_reason(test_mode, dry_run, delete_only):
    if test_mode:
        return "Test mode"
    if not dry_run and not delete_only:
        return "Full process complete"
    if delete_only:
        return "Delete-only mode complete"
    return "Cleanup"


def handle_exception(e, test_mode, delete_only):
    if test_mode:
        logger.info(
            "Error occurred during test mode: cleaning IdMapping table"
        )
        clean_id_mapping()
    if not test_mode:
        logger.warning("Error occurred but IdMapping table is preserved")

    operation_name = "deletion" if delete_only else "anonymization"
    logger.error(f"Error during {operation_name}: {e}")


def clean_id_mapping():
    try:
        IdMapping.query.delete()
        db.session.commit()
        logger.info("IdMapping table cleaned successfully")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error cleaning IdMapping table: {e}")
        raise
