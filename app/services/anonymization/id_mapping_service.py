from app import db
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
    def get_user_negative_id(original_id):
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
            int: New negative ID
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
            entity_type="user", original_id=original_id, anonymized_id=new_id
        )
        db.session.add(mapping)

        try:
            db.session.flush()
        except Exception as e:
            logger.error(f"Error during flush: {e}")
            db.session.rollback()

        return new_id

    @staticmethod
    def get_entity_positive_id(entity_type, original_id):
        """
        Get a positive ID for an entity from the anonymized_id_seq sequence.

        This method should be used for all non-user entities to maintain
        consistency with the user anonymization process.

        Args:
            entity_type: Entity type (e.g., "mission", "company")
            original_id: Original entity ID

        Returns:
            int: New positive ID
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

        logger.debug(
            f"Mapped {entity_type} ID {original_id} to positive ID {new_id}"
        )
        return new_id

    @staticmethod
    def get_mappings_for_entity_type(entity_type):
        """
        Get all mappings for a given entity type.

        Args:
            entity_type: Entity type (e.g., "user", "mission")

        Returns:
            dict: Dictionary {original_id: anonymized_id}
        """
        mappings = IdMapping.query.filter_by(entity_type=entity_type).all()
        return {
            mapping.original_id: mapping.anonymized_id for mapping in mappings
        }

    @staticmethod
    def get_all_mapped_ids(entity_type):
        """
        Get all original IDs that have been mapped for a specific entity type.

        Args:
            entity_type: Entity type (e.g., "user", "mission")

        Returns:
            Set[int]: Set of original IDs that have been mapped
        """
        result = (
            IdMapping.query.filter_by(entity_type=entity_type)
            .with_entities(IdMapping.original_id)
            .all()
        )
        return {row[0] for row in result}

    @staticmethod
    def clean_mappings():
        """
        Remove all mappings from the IdMapping table.
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
