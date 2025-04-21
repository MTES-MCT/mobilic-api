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
    if verbose:
        logger.setLevel(logging.DEBUG)

    try:
        cutoff_date = datetime.now() - relativedelta(
            years=years, months=months
        )

        log_operation_start(dry_run, test_mode, cutoff_date)

        if not handle_tables_cleaning(dry_run, test_mode, force_clean):
            return

        process_user_data(dry_run, test_mode, cutoff_date)

        handle_final_cleanup(dry_run, test_mode)

        logger.info("User anonymization completed successfully")

        if dry_run and not test_mode:
            logger.info(
                "Dry run completed: ID mappings created but no users were modified. "
                "To perform actual anonymization, run again with --no-dry-run flag."
            )

    except Exception as e:
        handle_exception(e, test_mode)
        raise


def log_operation_start(dry_run, test_mode, cutoff_date):
    """
    Log information about the operation being started.
    """
    log_prefix = ""

    if test_mode:
        log_prefix = "Test mode: "

    if dry_run:
        log_prefix += "Dry run: "

    threshold_info = f"{years} years"
    if months > 0:
        threshold_info += f" and {months} months"

    logger.info(
        f"{log_prefix}Starting user anonymization process "
        f"with cut-off date: {cutoff_date.date()} (threshold: {threshold_info})"
    )


def handle_tables_cleaning(dry_run, test_mode, force_clean):
    """
    Handle the cleaning of mapping tables based on mode and parameters.

    Returns:
        bool: Whether to proceed with the operation
    """
    mapping_count = IdMapping.query.count()

    should_clean_initial = mapping_count > 0 and not test_mode

    if should_clean_initial and not force_clean:
        logger.error(
            f"There are {mapping_count} existing mappings in IdMapping table. "
            f"Use --force-clean to proceed and clean existing mappings."
        )
        return False

    if should_clean_initial and force_clean:
        logger.info(
            f"Cleaning {mapping_count} existing mappings from IdMapping table"
        )
        if not dry_run:
            clean_id_mapping()

    return True


def process_user_data(dry_run, test_mode, cutoff_date):
    """
    Process user data for anonymization.
    """
    logger.info("Processing user data")

    logger.info("Starting user classification phase")
    classifier = UserClassifier(cutoff_date)
    classification = classifier.find_inactive_users()

    users_to_anon = classification["users"]
    admin_to_anon = classification["admins"]
    controller_to_anon = classification["controllers"]

    user_anonymizer = UserAnonymizer(db.session, dry_run=dry_run)

    user_anonymizer.anonymize_user_data(
        users_to_anon,
        admin_to_anon,
        controller_to_anon,
        test_mode,
    )


def handle_final_cleanup(dry_run, test_mode):
    """
    Handle final cleanup of the mapping table based on the execution mode.
    """
    if dry_run and not test_mode:
        mapping_count = IdMapping.query.count()
        logger.info(
            f"Dry run complete: preserving {mapping_count} mappings in IdMapping table "
            f"for future anonymization. Run again with --no-dry-run to perform actual anonymization."
        )
        return

    clean_reason = get_clean_reason(test_mode, dry_run)
    logger.info(f"{clean_reason}: cleaning IdMapping table")
    clean_id_mapping()


def get_clean_reason(test_mode, dry_run):
    """
    Get the reason for cleaning the mapping table.
    """
    if test_mode:
        return "Test mode"

    if not dry_run:
        return "Anonymization complete"

    return "Cleanup"


def handle_exception(e, test_mode):
    """
    Handle exceptions during the anonymization process.
    """
    if test_mode:
        logger.info(
            "Error occurred during test mode: cleaning IdMapping table"
        )
        clean_id_mapping()
    else:
        logger.warning("Error occurred but IdMapping table is preserved")

    logger.error(f"Error details: {str(e)}")
