from app import db
from typing import Set
from app.services.anonymization.standalone import AnonymizationExecutor
from app.services.anonymization.id_mapping_service import IdMappingService
import logging
from app.models import User
from app.models.user import UserAccountStatus
from datetime import datetime, time, timezone
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
    ) -> None:
        """
        Anonymize user data based on the specified user groups.

        Args:
            users_to_anon: Set of user IDs for anonymization
            admin_to_anon: Set of admin IDs for anonymization
            controller_to_anon: Set of controller IDs for anonymization
            test_mode: If True, roll back all changes at the end
        """
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
        - Sets user status to ANONYMIZED
        - Removes or obfuscates personal information
        - Preserves references and doesn't delete the original records
        - Creates ID mappings for each user with negative IDs

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
            IdMappingService.get_user_negative_id(user.id)

            if self.dry_run:
                continue

            date_only = user.creation_time.date()
            user.creation_time = datetime.combine(
                date_only, time(0, 0, 0)
            ).replace(tzinfo=timezone.utc)
            user.email = f"anon_{user.id}@anonymous.aa"
            user.first_name = "Anonymized"
            user.last_name = "User"
            user.phone_number = None
            user.france_connect_id = None
            user.france_connect_info = None
            user.activation_email_token = None
            user.password = str(uuid4())
            user.password_update_time = None
            user.ssn = None

            if user.way_heard_of_mobilic and not re.match(
                pattern, user.way_heard_of_mobilic
            ):
                user.way_heard_of_mobilic = "OTHER"

            user.status = UserAccountStatus.ANONYMIZED

            db.session.add(user)
