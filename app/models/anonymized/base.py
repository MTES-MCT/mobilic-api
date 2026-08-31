from app import db
import logging

logger = logging.getLogger(__name__)


class AnonymizedModel(db.Model):
    __abstract__ = True

    # None = not primed, check_existing_record falls back to per-row
    # SELECTs; a set is authoritative for the current loop
    _primed_existing_ids = None

    @classmethod
    def prime_existing_records(cls, anonymized_ids) -> None:
        ids = [i for i in anonymized_ids if i]
        cls._primed_existing_ids = (
            {
                row[0]
                for row in db.session.query(cls.id).filter(cls.id.in_(ids))
            }
            if ids
            else set()
        )

    @classmethod
    def clear_primed_records(cls) -> None:
        for subclass in cls.__subclasses__():
            subclass._primed_existing_ids = None

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

        if entity_type == "user":
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

        if (
            cls._primed_existing_ids is not None
            and entity_id not in cls._primed_existing_ids
        ):
            return None

        existing = db.session.query(cls).get(entity_id)
        if existing:
            logger.debug(
                f"Found existing {cls.__name__} record with ID {entity_id}"
            )
            return existing

        return None

    ACTIVITY_DURATION_BUCKET_SECONDS = 30 * 60

    @classmethod
    def bucket_end_time(cls, start_time, end_time):
        if start_time is None or end_time is None:
            return None
        delta_seconds = (end_time - start_time).total_seconds()
        bucket = cls.ACTIVITY_DURATION_BUCKET_SECONDS
        rounded = int(round(delta_seconds / bucket)) * bucket
        if delta_seconds > 0 and rounded == 0:
            rounded = bucket
        from datetime import timedelta

        return start_time + timedelta(seconds=rounded)

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
