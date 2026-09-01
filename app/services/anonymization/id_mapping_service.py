from app import db
from typing import Optional, Set, Dict, Tuple
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

    # must be cleared whenever mappings are deleted or rolled back
    _mapping_cache: Dict[Tuple[str, int], int] = {}

    @classmethod
    def clear_cache(cls) -> None:
        cls._mapping_cache.clear()

    @classmethod
    def prefetch_mappings(
        cls, entity_type: str, original_ids: Set[int]
    ) -> Dict[int, int]:
        """
        Resolve a whole set of mappings in 3 queries: one SELECT for
        existing ones, one nextval/generate_series allocation and one
        bulk insert for missing ones.

        Returns:
            Dict {original_id: anonymized_id}, also kept in cache
        """
        original_ids = {oid for oid in original_ids if oid}
        if not original_ids:
            return {}

        mappings = dict(
            db.session.query(IdMapping.original_id, IdMapping.anonymized_id)
            .filter(
                IdMapping.entity_type == entity_type,
                IdMapping.original_id.in_(original_ids),
            )
            .all()
        )

        missing = sorted(original_ids - set(mappings))
        if missing:
            sequence = cls.get_sequence_for_entity(entity_type)
            new_ids = [
                row[0]
                for row in db.session.execute(
                    f"SELECT nextval('{sequence}')"
                    " FROM generate_series(1, :n)",
                    {"n": len(missing)},
                )
            ]
            db.session.bulk_insert_mappings(
                IdMapping,
                [
                    {
                        "entity_type": entity_type,
                        "original_id": original_id,
                        "anonymized_id": new_id,
                        "deletion_target": False,
                    }
                    for original_id, new_id in zip(missing, new_ids)
                ],
            )
            mappings.update(zip(missing, new_ids))

        for original_id, new_id in mappings.items():
            cls._mapping_cache[(entity_type, original_id)] = new_id

        return mappings

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

        cached = IdMappingService._mapping_cache.get(("user", original_id))
        if cached is not None:
            return cached

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
            raise

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

        cached = IdMappingService._mapping_cache.get(
            (entity_type, original_id)
        )
        if cached is not None:
            return cached

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
    def get_sequence_for_entity(entity_type: str) -> str:
        """Users get negative IDs from a dedicated sequence, other entities
        get positive IDs."""
        return (
            "negative_user_id_seq"
            if entity_type == "user"
            else "anonymized_id_seq"
        )

    @staticmethod
    def mark_all_for_deletion(
        entity_type: str, original_ids: Set[int]
    ) -> None:
        """
        Mark a whole set of entities as deletion targets in a single upsert.

        Creates missing mappings (allocating anonymized IDs from the proper
        sequence) and upgrades existing ones to deletion_target=TRUE. The
        flag is never downgraded, making the operation idempotent.

        Args:
            entity_type: Entity type (e.g., "mission", "company")
            original_ids: Set of original entity IDs
        """
        original_ids = {oid for oid in original_ids if oid}
        if not original_ids:
            return

        sequence = IdMappingService.get_sequence_for_entity(entity_type)
        db.session.execute(
            f"""
            INSERT INTO temp_id_mapping
                (entity_type, original_id, anonymized_id, deletion_target)
            SELECT :entity_type, v.id, nextval('{sequence}'), TRUE
            FROM (SELECT DISTINCT unnest(:ids) AS id) v
            ON CONFLICT (entity_type, original_id)
            DO UPDATE SET deletion_target = TRUE
            """,
            {"entity_type": entity_type, "ids": list(original_ids)},
        )

        # The raw upsert bypasses the identity map: expire cached mappings
        # so ORM readers see the updated deletion_target
        for obj in db.session.identity_map.values():
            if isinstance(obj, IdMapping):
                db.session.expire(obj)

    # Every id referenced by the set-based copies must be seeded here first
    MISSION_SUBTREE_MAPPING_SOURCES = [
        (
            "activity",
            "SELECT a.id FROM activity a WHERE a.mission_id = ANY(:mids)",
        ),
        (
            "activity_version",
            """SELECT av.id FROM activity_version av
               JOIN activity a ON a.id = av.activity_id
               WHERE a.mission_id = ANY(:mids)""",
        ),
        (
            "mission_end",
            "SELECT me.id FROM mission_end me"
            " WHERE me.mission_id = ANY(:mids)",
        ),
        (
            "mission_validation",
            "SELECT mv.id FROM mission_validation mv"
            " WHERE mv.mission_id = ANY(:mids)",
        ),
        (
            "location_entry",
            "SELECT le.id FROM location_entry le"
            " WHERE le.mission_id = ANY(:mids)",
        ),
        (
            "user",
            """SELECT r.id FROM (
                 SELECT user_id AS id FROM activity
                   WHERE mission_id = ANY(:mids)
                 UNION SELECT submitter_id FROM activity
                   WHERE mission_id = ANY(:mids)
                 UNION SELECT av.submitter_id FROM activity_version av
                   JOIN activity a ON a.id = av.activity_id
                   WHERE a.mission_id = ANY(:mids)
                 UNION SELECT submitter_id FROM mission
                   WHERE id = ANY(:mids)
                 UNION SELECT user_id FROM mission_end
                   WHERE mission_id = ANY(:mids)
                 UNION SELECT submitter_id FROM mission_end
                   WHERE mission_id = ANY(:mids)
                 UNION SELECT user_id FROM mission_validation
                   WHERE mission_id = ANY(:mids)
                 UNION SELECT submitter_id FROM mission_validation
                   WHERE mission_id = ANY(:mids)
                 UNION SELECT submitter_id FROM location_entry
                   WHERE mission_id = ANY(:mids)
               ) r WHERE r.id IS NOT NULL""",
        ),
        (
            "company",
            "SELECT DISTINCT m.company_id AS id FROM mission m"
            " WHERE m.id = ANY(:mids)",
        ),
        (
            "address",
            "SELECT DISTINCT le.address_id AS id FROM location_entry le"
            " WHERE le.mission_id = ANY(:mids)",
        ),
        (
            "company_known_address",
            """SELECT DISTINCT le.company_known_address_id AS id
               FROM location_entry le
               WHERE le.mission_id = ANY(:mids)
                 AND le.company_known_address_id IS NOT NULL""",
        ),
    ]

    @staticmethod
    def seed_mission_subtree_mappings(mission_ids: Set[int]) -> None:
        """
        Create every id mapping needed by the set-based copies of the
        mission subtree, one INSERT...SELECT per entity type.

        Existing mappings are left untouched (DO NOTHING never downgrades
        deletion_target); the NOT EXISTS guard avoids burning sequence
        values for already-mapped ids.

        Args:
            mission_ids: Set of mission IDs driving the subtree
        """
        mission_ids = {mid for mid in mission_ids if mid}
        if not mission_ids:
            return

        params = {"mids": list(mission_ids)}
        for (
            entity_type,
            select_sql,
        ) in IdMappingService.MISSION_SUBTREE_MAPPING_SOURCES:
            sequence = IdMappingService.get_sequence_for_entity(entity_type)
            db.session.execute(
                f"""
                INSERT INTO temp_id_mapping
                    (entity_type, original_id, anonymized_id)
                SELECT :entity_type, src.id, nextval('{sequence}')
                FROM ({select_sql}) src
                WHERE NOT EXISTS (
                    SELECT 1 FROM temp_id_mapping t
                    WHERE t.entity_type = :entity_type
                      AND t.original_id = src.id
                )
                ON CONFLICT (entity_type, original_id) DO NOTHING
                """,
                {"entity_type": entity_type, **params},
            )

    @staticmethod
    def mark_for_deletion(entity_type: str, original_id: int) -> None:
        """
        Explicitly mark an entity as a target for deletion.

        Args:
            entity_type: Entity type (e.g., "mission", "company")
            original_id: Original entity ID
        """
        IdMappingService.mark_all_for_deletion(entity_type, {original_id})

    @staticmethod
    def clean_mappings() -> int:
        """
        Remove all mappings from the IdMapping table.

        Returns:
            int: Number of mappings removed
        """
        IdMappingService.clear_cache()
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
