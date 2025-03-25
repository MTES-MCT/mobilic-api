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

logger = logging.getLogger(__name__)

years = app.config["ANONYMIZATION_THRESHOLD_YEAR"]
months = app.config["ANONYMIZATION_THRESHOLD_MONTH"]


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


def clean_id_mapping():
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


def anonymize_users(
    verbose: bool = False,
    dry_run: bool = True,
    verify_only: bool = False,
    test_mode: bool = False,
    force_clean: bool = False,
) -> None:
    """
    Anonymize user data that has been inactive for a specified period.

    Args:
        verbose: Enable verbose mode for more detailed logs
        dry_run: Dry-run mode - simulate anonymization without actual changes (default: True)
        verify_only: Verify-only mode - verify anonymization status
        test_mode: Test mode - roll back all changes at the end
        force_clean: Clean mapping table before starting

    Workflow for effective anonymization:
    1. Run with dry_run=True to simulate anonymization
    2. Run with dry_run=False to perform actual anonymization
    3. Run with verify_only=True to verify anonymization status
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    if not dry_run and verify_only:
        logger.warning(
            "Invalid combination: Verify-only mode cannot be used with no-dry-run. "
            "The verify-only mode works with the default dry-run setting."
        )
        return

    if verify_only and not IdMapping.query.count():
        logger.error(
            "Cannot run in verify-only mode: No mappings found in IdMapping table. "
            "Run first in dry-run mode or normal mode to create the necessary mappings."
        )
        return

    try:
        cutoff_date = datetime.now() - relativedelta(
            years=years, months=months
        )

        log_operation_start(dry_run, verify_only, test_mode, cutoff_date)

        if not handle_tables_cleaning(
            dry_run, verify_only, test_mode, force_clean
        ):
            return

        process_user_data(dry_run, verify_only, test_mode, cutoff_date)

        handle_final_cleanup(dry_run, verify_only, test_mode)

        operation_name = "verification" if verify_only else "anonymization"
        logger.info(f"User {operation_name} completed successfully")

        if dry_run and not verify_only and not test_mode:
            logger.info(
                "Dry run completed. To perform actual anonymization, "
                "run again with --no-dry-run flag."
            )

    except Exception as e:
        handle_exception(e, test_mode, verify_only)
        raise


def log_operation_start(dry_run, verify_only, test_mode, cutoff_date):
    """
    Log information about the operation being started.
    """
    log_prefix = ""

    if test_mode:
        log_prefix = "Test mode: "

    if dry_run:
        log_prefix += "Dry run: "

    operation_name = "verification" if verify_only else "anonymization"

    threshold_info = f"{years} years"
    if months > 0:
        threshold_info += f" and {months} months"

    logger.info(
        f"{log_prefix}Starting user {operation_name} process "
        f"with cut-off date: {cutoff_date.date()} (threshold: {threshold_info})"
    )


def handle_tables_cleaning(dry_run, verify_only, test_mode, force_clean):
    """
    Handle the cleaning of mapping tables based on mode and parameters.

    Returns:
        bool: Whether to proceed with the operation
    """
    mapping_count = IdMapping.query.count()

    if verify_only and mapping_count == 0:
        logger.error("Cannot verify: No existing mappings found")
        return False

    should_clean_initial = (
        not verify_only and mapping_count > 0 and not test_mode
    )

    if should_clean_initial and not force_clean:
        logger.error(
            f"There are {mapping_count} existing mappings in IdMapping table. "
            f"Use --force-clean to proceed and clean existing mappings. "
            f"Alternatively, use --verify-only to verify the anonymization status."
        )
        return False

    if should_clean_initial and force_clean:
        logger.info(
            f"Cleaning {mapping_count} existing mappings from IdMapping table"
        )
        if not dry_run:
            clean_id_mapping()

    return True


def process_user_data(dry_run, verify_only, test_mode, cutoff_date):
    """
    Process user data either by anonymizing or verifying.
    """
    operation_type = "Verifying" if verify_only else "Processing"
    logger.info(f"{operation_type} user data")

    full_anon_users = set()
    partial_anon_users = set()
    controller_anon_users = set()

    if not verify_only:
        logger.info("Starting user classification phase")
        classifier = UserClassifier(cutoff_date)
        classification = classifier.classify_users_for_anonymization()

        full_anon_users = classification["user_full_anonymization"]
        partial_anon_users = classification["user_partial_anonymization"]
        controller_anon_users = classification["controller_user_anonymization"]

        log_classification_results(
            full_anon_users, partial_anon_users, controller_anon_users
        )

    user_anonymizer = UserAnonymizer(db.session, dry_run=dry_run)

    user_anonymizer.anonymize_user_data(
        full_anon_users,
        partial_anon_users,
        controller_anon_users,
        test_mode,
        verify_only,
    )


def handle_final_cleanup(dry_run, verify_only, test_mode):
    """
    Handle final cleanup of the mapping table based on the execution mode.
    """
    if dry_run and not verify_only and not test_mode:
        mapping_count = IdMapping.query.count()
        logger.info(
            f"Dry run complete: preserving {mapping_count} mappings in IdMapping table "
            f"for future verification. Run again with --no-dry-run to perform actual anonymization."
        )
        return

    if verify_only and test_mode:
        mapping_count = IdMapping.query.count()
        logger.info(
            f"Test mode verify-only complete: preserving {mapping_count} mappings in IdMapping table "
            f"for future test runs."
        )
        return

    if test_mode or (not dry_run and not verify_only):
        clean_reason = get_clean_reason(test_mode, dry_run, verify_only)
        logger.info(f"{clean_reason}: cleaning IdMapping table")
        clean_id_mapping()


def get_clean_reason(test_mode, dry_run, verify_only):
    """
    Get the reason for cleaning the mapping table.
    """
    if test_mode:
        return "Test mode"

    if not dry_run:
        return "Anonymization complete"

    if verify_only:
        return "Verification complete"

    return "Cleanup"


def handle_exception(e, test_mode, verify_only):
    """
    Handle exceptions during the anonymization process.
    """
    if test_mode and not verify_only:
        logger.info(
            "Error occurred during test mode: cleaning IdMapping table"
        )
        clean_id_mapping()

    if test_mode and verify_only:
        logger.info(
            "Error occurred during verify-only test mode: preserving IdMapping table for future test runs"
        )

    if not test_mode:
        logger.warning("Error occurred but IdMapping table is preserved")

    logger.error(f"Error details: {str(e)}")
