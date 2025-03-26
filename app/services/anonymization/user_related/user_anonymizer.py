from app import db
from typing import Set, Dict
from app.services.anonymization.standalone import AnonymizationExecutor
from app.services.anonymization.id_mapping_service import IdMappingService
import logging
from app.models import User
from app.models.user import UserAccountStatus

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
        """
        Anonymize user data based on the specified user groups.

        Args:
            full_anonymization_users: Set of user IDs for full anonymization
            partial_anonymization_users: Set of user IDs for partial anonymization
            controller_anonymization_users: Set of controller IDs for anonymization
            test_mode: If True, roll back all changes at the end
            verify_only: If True, only verify that users are properly anonymized
        """
        if verify_only:
            logger.info("Running in verify-only mode")
            verification_result = self.verify_users_anonymization(
                verify_only=True
            )
            if verification_result:
                logger.info(
                    "Verification successful: all users are properly anonymized"
                )
            if not verification_result:
                logger.warning(
                    "Verification failed: some users are not properly anonymized"
                )
            return

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

        self.anonymize_users_in_place(user_ids)

    def anonymize_users_in_place(self, user_ids: Set[int]) -> None:
        """
        Anonymize users by modifying their records in place.

        This method implements the approach to user anonymization:
        - Assigns negative IDs to users (via database negative_user_id_seq sequence)
        - Sets user status to ANONYMIZED
        - Removes or obfuscates personal information
        - Preserves references and doesn't delete the original records

        Args:
            user_ids: Set of user IDs to anonymize
        """
        if not user_ids:
            return

        users = User.query.filter(User.id.in_(user_ids)).all()

        logger.info(f"Anonymizing {len(users)} users in place")
        if not users:
            return

        for user in users:
            negative_id = IdMappingService.get_user_negative_id(user.id)

            logger.info(f"Anonymizing user {user.id} to {negative_id}")

            user.email = f"anonymized_{negative_id}@example.com"
            user.first_name = "Anonymized"
            user.last_name = "User"
            user.has_confirmed_email = False
            user.has_activated_email = False
            user.phone_number = None
            user.france_connect_id = None
            user.france_connect_info = None
            user.activation_email_token = None
            user.password = None
            user.ssn = None
            user.way_heard_of_mobilic = None

            user.status = UserAccountStatus.ANONYMIZED

            db.session.add(user)

    def verify_users_anonymization(self, verify_only: bool = False) -> bool:
        """
        Verify that users have been properly anonymized.

        This method checks that:
        1. All users marked for anonymization have been processed
        2. All anonymized users have the correct status
        3. All anonymized users have no personal information

        Args:
            verify_only: If True, only perform verification without any updates

        Returns:
            bool: True if all checks pass, False otherwise
        """
        if not verify_only:
            logger.info(
                "Skipping verification as verify_only mode is disabled"
            )
            return True

        user_mapping_ids = IdMappingService.get_all_mapped_ids("user")

        if not user_mapping_ids:
            logger.warning("No user mappings found, nothing to verify")
            return False

        logger.info(
            f"Verifying anonymization for {len(user_mapping_ids)} users"
        )

        anonymized_users = User.query.filter(
            User.id.in_(user_mapping_ids)
        ).all()

        if len(anonymized_users) != len(user_mapping_ids):
            logger.error(
                f"Found {len(anonymized_users)} users but expected {len(user_mapping_ids)}. "
                f"Some users may have been deleted instead of anonymized."
            )
            return False

        for user in anonymized_users:
            if user.status != UserAccountStatus.ANONYMIZED:
                logger.error(
                    f"User {user.id} has status {user.status} but should be {UserAccountStatus.ANONYMIZED}"
                )
                return False

            if user.email and not user.email.startswith("anonymized_"):
                logger.error(
                    f"User {user.id} has non-anonymized email: {user.email}"
                )
                return False

            if user.first_name != "Anonymized" or user.last_name != "User":
                logger.error(
                    f"User {user.id} has non-anonymized name: {user.first_name} {user.last_name}"
                )
                return False

            if user.phone_number or user.france_connect_id or user.ssn:
                logger.error(f"User {user.id} still has personal information")
                return False

        logger.info("All users have been properly anonymized")
        return True
