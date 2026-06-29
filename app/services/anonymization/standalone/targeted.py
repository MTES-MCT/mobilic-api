"""
Targeted deletion for ad-hoc support operations: delete specific companies
by ID list, outside of the cutoff-driven nightly job.

Used for support tickets that want to remove empty/test companies polluting
stats. No anonymization audit trail is kept (use the standard nightly
pipeline if you need that). User accounts (table `user`) are NEVER modified.
"""

import logging
from typing import Iterable

from sqlalchemy import text

from app import db
from app.services.anonymization.standalone.anonymization_executor import (
    AnonymizationExecutor,
)

logger = logging.getLogger(__name__)


def delete_specific_companies(
    company_ids: Iterable[int],
    test_mode: bool = False,
) -> None:
    """
    Delete companies whose IDs are given explicitly, along with their direct
    dependencies (teams, vehicles, certifications, missions+activities,
    employments, …). Employments are first stamped with end_date=CURRENT_DATE
    so the link looks cleanly terminated in any historical view. User rows
    are NEVER touched.

    Args:
        company_ids: IDs of companies to delete. Empty iterable is a no-op.
        test_mode: If True, roll back the transaction at the end. Useful for
            smoke tests on a real DB.
    """
    company_ids = set(company_ids)
    if not company_ids:
        logger.info("No company_id provided, nothing to delete")
        return

    logger.info(
        "Targeted deletion: %d company(ies), test_mode=%s",
        len(company_ids),
        test_mode,
    )

    # AnonymizationExecutor exposes the delete_* helpers we need; dry_run
    # must be False so they actually run.
    executor = AnonymizationExecutor(db.session, dry_run=False)
    try:
        ids_param = list(company_ids)
        mission_ids = {
            r[0]
            for r in db.session.execute(
                text("SELECT id FROM mission WHERE company_id = ANY(:ids)"),
                {"ids": ids_param},
            ).fetchall()
        }
        employment_ids = {
            r[0]
            for r in db.session.execute(
                text("SELECT id FROM employment WHERE company_id = ANY(:ids)"),
                {"ids": ids_param},
            ).fetchall()
        }
        logger.info(
            "Found %d mission(s) and %d employment(s) attached",
            len(mission_ids),
            len(employment_ids),
        )

        if employment_ids:
            detached = db.session.execute(
                text(
                    "UPDATE employment "
                    "SET end_date = CURRENT_DATE "
                    "WHERE id = ANY(:ids) AND end_date IS NULL"
                ),
                {"ids": list(employment_ids)},
            ).rowcount
            if detached:
                logger.info("Detached %d employment(s) via end_date", detached)
            db.session.flush()

        # Canonical order (mirrors DataFinder.delete_anonymized_data):
        # missions -> employments -> companies. Each *_and_dependencies
        # call handles its own emails / third-party links / activities.
        # Two FK tables are NOT covered by those helpers (they only appear
        # via the standard cutoff-based job, where the rows are already
        # gone): mission_auto_validation and third_party_client_company.
        # We clean them by hand here.
        if mission_ids:
            db.session.execute(
                text(
                    "DELETE FROM mission_auto_validation "
                    "WHERE mission_id = ANY(:ids)"
                ),
                {"ids": list(mission_ids)},
            )
            executor.delete_mission_and_dependencies(mission_ids)
            db.session.flush()
        if employment_ids:
            executor.delete_employment_and_dependencies(employment_ids)
            db.session.flush()
        db.session.execute(
            text(
                "DELETE FROM third_party_client_company "
                "WHERE company_id = ANY(:ids)"
            ),
            {"ids": ids_param},
        )
        executor.delete_company_and_dependencies(company_ids)

        if test_mode:
            logger.info("test_mode: rolling back")
            db.session.rollback()
        else:
            db.session.commit()
    except Exception:
        db.session.rollback()
        raise
