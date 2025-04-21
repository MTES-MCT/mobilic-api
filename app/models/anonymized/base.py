from app import db
import logging

logger = logging.getLogger(__name__)


class AnonymizedModel(db.Model):
    __abstract__ = True

    @classmethod
    def get_new_id(cls, entity_type: str, old_id: int):
        """
        Get a new ID for the entity using IdMappingService.

        Uses negative sequence for users, positive sequence for other entities.
        This ensures that references to users in anonymized tables are consistent
        with the negative IDs assigned during user anonymization.

        Args:
            entity_type: Entity type (e.g., "user", "mission")
            old_id: Original ID

        Returns:
            int: New anonymized ID (negative for users, positive for other entities)
        """
        if not old_id:
            return None

        from app.services.anonymization.id_mapping_service import (
            IdMappingService,
        )

        if entity_type in ("user", "anon_user"):
            return IdMappingService.get_user_negative_id(old_id)
        else:
            return IdMappingService.get_entity_positive_id(entity_type, old_id)

    @classmethod
    def check_existing_record(cls, entity_id):
        """
        Check if a record with the given ID already exists in the anonymized table.

        Args:
            entity_id: ID to check for

        Returns:
            The existing record if found, None otherwise
        """
        if not entity_id:
            return None

        existing = db.session.query(cls).get(entity_id)
        if existing:
            logger.debug(
                f"Found existing {cls.__name__} record with ID {entity_id}"
            )
            return existing

        return None

    @staticmethod
    def truncate_to_month(date):
        """
        Truncate a date to the first day of the month to reduce precision
        for anonymization purposes.

        Args:
            date: Date to truncate

        Returns:
            Date truncated to the first day of the month
        """
        if date is None:
            return None
        if hasattr(date, "hour"):
            return date.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        return date.replace(day=1)
