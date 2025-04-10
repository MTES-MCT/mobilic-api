from app import db
from typing import Set
from app.services.anonymization.standalone import AnonymizationExecutor
from app.services.anonymization.id_mapping_service import IdMappingService
import logging
from app.models import User
from app.models.user import UserAccountStatus
from uuid import uuid4
import re

logger = logging.getLogger(__name__)


class UserAnonymizer(AnonymizationExecutor):
    def anonymize_user_data(
        self,
        users_to_anon: Set[int],
        admin_to_anon: Set[int],
        controller_to_anon: Set[int],
        test_mode: bool = False,
        verify_only: bool = False,
    ) -> None:
        """
        Anonymize user data based on the specified user groups.

        Args:
            users_to_anon: Set of user IDs for anonymization
            admin_to_anon: Set of admin IDs for anonymization
            controller_to_anon: Set of controller IDs for anonymization
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
            if users_to_anon:
                logger.info(f"Processing {len(users_to_anon)} non-admin users")
                self.anonymize_users_in_place(users_to_anon)

            if admin_to_anon:
                logger.info(f"Processing {len(admin_to_anon)} admin")
                self.anonymize_users_in_place(admin_to_anon)

            if controller_to_anon:
                logger.info(
                    f"Processing {len(controller_to_anon)} controllers"
                )
                self.anonymize_controller_and_dependencies(controller_to_anon)

            if not any(
                [
                    users_to_anon,
                    admin_to_anon,
                    controller_to_anon,
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

        # Authorize only uppercase with underscore to ensure comptability with const WAY_HEARD_OF_MOBILIC_CHOICES in web/common/WayHeardOfMobilic.js
        pattern = r"^[A-Z]+(_[A-Z]+)+$|^[A-Z]+_[A-Z]+$"

        for user in users:
            negative_id = IdMappingService.get_user_negative_id(user.id)

            user.email = f"anonymized_{negative_id}@example.com"
            user.first_name = "Anonymized"
            user.last_name = "User"
            user.has_confirmed_email = True
            user.has_activated_email = True
            user.phone_number = None
            user.france_connect_id = None
            user.france_connect_info = None
            user.activation_email_token = None
            user.password = str(uuid4())
            user.ssn = None

            if user.way_heard_of_mobilic and not re.match(
                pattern, user.way_heard_of_mobilic
            ):
                user.way_heard_of_mobilic = "OTHER"

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

        return self._verify_all_users_anonymized(anonymized_users)

    def _verify_all_users_anonymized(self, anonymized_users):
        """Helper method to check if all users are properly anonymized."""
        for user in anonymized_users:
            if not self._is_user_properly_anonymized(user):
                return False
        return True

    def _is_user_properly_anonymized(self, user):
        """Check if a single user is properly anonymized."""
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

        if not user.has_confirmed_email or not user.has_activated_email:
            logger.error(
                f"User {user.id} column has_confirmed_email (current value: {user.has_confirmed_email}) "
                f"and has_activated_email (current value: {user.has_activated_email}) "
                f"must be true for retro-compatibility"
            )
            return False

        if user.phone_number or user.france_connect_id or user.ssn:
            logger.error(f"User {user.id} still has personal information")
            return False

        if user.password is None:
            logger.error(f"User {user.id} has no password: security alert")
            return False

        return True
