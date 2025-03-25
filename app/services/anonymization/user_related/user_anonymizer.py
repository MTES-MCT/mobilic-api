from app import db
from typing import Set, Dict, Tuple, List
from app.services.anonymization.standalone import AnonymizationExecutor
import logging
from app.models import User
from app.models.user import UserAccountStatus
from sqlalchemy.sql import text
from datetime import datetime

logger = logging.getLogger(__name__)


class UserAnonymizer(AnonymizationExecutor):
    def anonymize_user_data(
        self,
        full_anonymization_users: Set[int],
        partial_anonymization_users: Set[int],
        controller_anonymization_users: Set[int],
        test_mode: bool = False,
        verify_only: bool = False,
    ) -> None:
        transaction = db.session.begin_nested()
        try:
            if full_anonymization_users:
                self._process_full_anonymization(full_anonymization_users)

            if controller_anonymization_users:
                logger.info(
                    f"Processing {len(controller_anonymization_users)} controllers"
                )
                self.anonymize_controller_and_dependencies(
                    controller_anonymization_users
                )

            if not any(
                [
                    full_anonymization_users,
                    partial_anonymization_users,
                    controller_anonymization_users,
                ]
            ):
                logger.info("No user data to anonymize")
                transaction.rollback()
                return

            if test_mode:
                logger.info("Test mode: rolling back changes")
                transaction.rollback()
                db.session.rollback()
            if not test_mode:
                logger.info("Committing user data changes...")
                transaction.commit()
                db.session.commit()

        except Exception as e:
            logger.error(f"Error processing user data: {e}")
            transaction.rollback()
            db.session.rollback()
            raise

    def _find_related_data(self, user_ids: Set[int]) -> Dict[str, Set[int]]:
        activity_mission_query = """
        SELECT DISTINCT a.mission_id 
        FROM activity a 
        WHERE a.user_id = ANY(:user_ids)
           OR a.submitter_id = ANY(:user_ids)
           OR a.dismiss_author_id = ANY(:user_ids)
        """

        mission_query = """
        SELECT DISTINCT m.id 
        FROM mission m
        WHERE m.submitter_id = ANY(:user_ids)
        """

        mission_validation_query = """
        SELECT DISTINCT mv.mission_id
        FROM mission_validation mv
        WHERE mv.submitter_id = ANY(:user_ids)
           OR mv.user_id = ANY(:user_ids)
        """

        employment_query = """
        SELECT DISTINCT e.id
        FROM employment e
        WHERE e.user_id = ANY(:user_ids)
           OR e.submitter_id = ANY(:user_ids)
           OR e.dismiss_author_id = ANY(:user_ids)
        """

        params = {"user_ids": list(user_ids)}

        results = {
            "activity_missions": db.session.execute(
                activity_mission_query, params
            ),
            "direct_missions": db.session.execute(mission_query, params),
            "validation_missions": db.session.execute(
                mission_validation_query, params
            ),
            "employments": db.session.execute(employment_query, params),
        }

        mission_ids = set()
        mission_ids.update(
            row[0]
            for row in results["activity_missions"]
            if row[0] is not None
        )
        mission_ids.update(row[0] for row in results["direct_missions"])
        mission_ids.update(row[0] for row in results["validation_missions"])

        employment_ids = {row[0] for row in results["employments"]}

        self._log_findings(mission_ids, employment_ids)

        return {"mission_ids": mission_ids, "employment_ids": employment_ids}

    def _log_findings(
        self, mission_ids: Set[int], employment_ids: Set[int]
    ) -> None:
        findings = {
            "missions": len(mission_ids),
            "employments": len(employment_ids),
        }

        for entity, count in findings.items():
            if count > 0:
                logger.info(f"Found {count} {entity} to anonymize")
            else:
                logger.info(f"No {entity} found")

    def _process_full_anonymization(self, user_ids: Set[int]) -> None:
        logger.info(f"Processing {len(user_ids)} users for full anonymization")

        related_data = self._find_related_data(user_ids)

        if related_data["mission_ids"]:
            self.anonymize_mission_and_dependencies(
                related_data["mission_ids"]
            )

        if related_data["employment_ids"]:
            self.anonymize_employment_and_dependencies(
                related_data["employment_ids"]
            )

        self.anonymize_user_and_dependencies(user_ids)
