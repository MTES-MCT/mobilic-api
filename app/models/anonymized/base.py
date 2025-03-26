from app import db


class AnonymizedModel(db.Model):
    __abstract__ = True

    @classmethod
    def get_new_id(cls, entity_type: str, old_id: int):
        """
        Get a new ID for the entity using IdMappingService.

        Uses negative sequence for users, positive sequence for other entities.

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
        if entity_type != "user":
            return IdMappingService.get_entity_positive_id(entity_type, old_id)

    @staticmethod
    def truncate_to_month(date):
        if date is None:
            return None
        if hasattr(date, "hour"):
            return date.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        return date.replace(day=1)
