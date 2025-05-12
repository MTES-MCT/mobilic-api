from app import db
from typing import Optional, Set, Dict
from app.models.anonymized.id_mapping import IdMapping
import logging

logger = logging.getLogger(__name__)


class IdMappingService:
    """
    Centralized service for managing ID mappings during anonymization.

    This service provides methods to:
    - Get negative IDs for users via negative_user_id_seq
    - Get positive IDs for other entities via anonymized_id_seq
    - Manage mappings in the IdMapping table

    IMPORTANT: This service ensures that:
    1. User IDs are consistently negative across all anonymization processes
    2. Non-user entity IDs are consistently positive
    3. References between anonymized tables maintain their integrity

    This consistent approach allows proper relationships between:
    - Users anonymized in-place (with negative IDs)
    - Entities in anonymized tables that reference those users
    """

    @staticmethod
    def get_user_negative_id(original_id: int) -> Optional[int]:
        """
        Get a negative ID for a user from the negative_user_id_seq sequence.

        This method is critical for maintaining consistency between:
        - Users anonymized in-place (user_related process)
        - References to users in anonymized tables (standalone process)

        Always use this method when mapping user IDs to ensure negative IDs
        are used consistently throughout the system.

        Args:
            original_id: Original user ID

        Returns:
            int: New negative ID or None if original_id is None
        """
        if not original_id:
            return None

        mapping = IdMapping.query.filter_by(
            entity_type="user", original_id=original_id
        ).one_or_none()

        if mapping is not None:
            return mapping.anonymized_id

        try:
            result = db.session.execute(
                "SELECT nextval('negative_user_id_seq')"
            )
            new_id = result.scalar()
        except Exception as e:
            logger.error(f"Could not use negative_user_id_seq: {e}")
            db.session.rollback()
            raise

        mapping = IdMapping(
            entity_type="user",
            original_id=original_id,
            anonymized_id=new_id,
        )
        db.session.add(mapping)

        try:
            db.session.flush()
        except Exception as e:
            logger.error(f"Error during flush: {e}")
            db.session.rollback()

        return new_id

    @staticmethod
    def get_entity_positive_id(
        entity_type: str, original_id: int
    ) -> Optional[int]:
        """
        Get a positive ID for an entity from the anonymized_id_seq sequence.

        This method should be used for all non-user entities to maintain
        consistency with the user anonymization process.

        Args:
            entity_type: Entity type (e.g., "mission", "company")
            original_id: Original entity ID

        Returns:
            int: New positive ID or None if original_id is None
        """
        if not original_id:
            return None

        mapping = IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).one_or_none()

        if mapping is not None:
            return mapping.anonymized_id

        try:
            result = db.session.execute("SELECT nextval('anonymized_id_seq')")
            new_id = result.scalar()
        except Exception as e:
            logger.error(f"Could not use anonymized_id_seq: {e}")
            db.session.rollback()
            raise

        mapping = IdMapping(
            entity_type=entity_type,
            original_id=original_id,
            anonymized_id=new_id,
        )
        db.session.add(mapping)

        try:
            db.session.flush()
        except Exception as e:
            logger.error(f"Error during flush: {e}")
            db.session.rollback()
            raise

        return new_id

    @staticmethod
    def get_deletion_target_ids(entity_type: str) -> Set[int]:
        """
        Get only the original IDs that are marked as deletion targets for a specific entity type.

        This method is critical for ensuring that only entities explicitly marked for
        deletion are removed, preventing accidental deletion of referenced entities.

        Args:
            entity_type: Entity type (e.g., "user", "mission")

        Returns:
            Set[int]: Set of original IDs that are marked as deletion targets
        """
        result = (
            IdMapping.query.filter_by(
                entity_type=entity_type, deletion_target=True
            )
            .with_entities(IdMapping.original_id)
            .all()
        )

        return {row[0] for row in result}

    @staticmethod
    def mark_for_deletion(entity_type: str, original_id: int) -> None:
        """
        Explicitly mark an entity as a target for deletion.

        This is the ONLY method that should be used to mark entities for deletion.
        It ensures a clear separation between ID mapping (which doesn't involve deletion)
        and explicitly marking entities for deletion.

        Args:
            entity_type: Entity type (e.g., "mission", "company")
            original_id: Original entity ID
        """
        if not original_id:
            return

        mapping = IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).one_or_none()

        if mapping is not None:
            if not mapping.deletion_target:
                mapping.deletion_target = True
            return

        if entity_type == "user":
            IdMappingService.get_user_negative_id(original_id)
        else:
            IdMappingService.get_entity_positive_id(entity_type, original_id)

        mapping = IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).one()
        mapping.deletion_target = True
        db.session.flush()

    @staticmethod
    def clean_mappings() -> int:
        """
        Remove all mappings from the IdMapping table.

        Returns:
            int: Number of mappings removed
        """
        try:
            count = IdMapping.query.count()
            IdMapping.query.delete()
            db.session.commit()
            logger.info(f"Removed {count} mappings from IdMapping table")
            return count
        except Exception as e:
            logger.error(f"Error cleaning IdMapping table: {e}")
            db.session.rollback()
            return 0
