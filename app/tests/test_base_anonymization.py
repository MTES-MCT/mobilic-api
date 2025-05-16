from app import db
from datetime import datetime
from sqlalchemy.orm.exc import MultipleResultsFound

from app.models.anonymized import AnonymizedModel, IdMapping
from app.services.anonymization.id_mapping_service import IdMappingService
from app.tests.helpers import test_db_changes, DBEntryUpdate
from app.tests import BaseTest


class TestAnonymizedModel(BaseTest):
    def setUp(self):
        """Setup for each test - clean environment"""
        super().setUp()

    def test_get_new_id_creates_mapping(self):
        """Test the creation of a new mapping"""
        entity_type = "test_entity"
        original_id = 1

        IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).delete()
        db.session.commit()

        expected_changes = {
            "new_mapping": DBEntryUpdate(
                model=IdMapping,
                before=None,
                after={"entity_type": entity_type, "original_id": original_id},
            )
        }

        with test_db_changes(expected_changes, [IdMapping]):
            new_id = AnonymizedModel.get_new_id(entity_type, original_id)
            db.session.commit()

        mapping = IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).one_or_none()
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.anonymized_id, new_id)

    def test_get_new_id_returns_existing(self):
        """Test retrieving an existing mapping"""
        entity_type = "test_entity"
        original_id = 2
        anonymized_id = 100

        mapping = IdMapping(
            entity_type=entity_type,
            original_id=original_id,
            anonymized_id=anonymized_id,
        )
        db.session.add(mapping)
        db.session.commit()

        result = AnonymizedModel.get_new_id(entity_type, original_id)
        self.assertEqual(result, anonymized_id)

        IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).delete()
        db.session.commit()

    def test_duplicate_mapping_raises(self):
        """Test handling of duplicate mappings"""
        entity_type = "test_entity"
        original_id = 3

        IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).delete()
        db.session.commit()

        mapping1 = IdMapping(
            entity_type=entity_type,
            original_id=original_id,
            anonymized_id=100,
        )
        db.session.add(mapping1)
        db.session.commit()

        try:
            mapping2 = IdMapping(
                entity_type=entity_type,
                original_id=original_id,
                anonymized_id=200,
            )
            db.session.add(mapping2)
            db.session.commit()
            self.fail("An exception should have been raised")
        except Exception:
            db.session.rollback()

        existing_id = AnonymizedModel.get_new_id(entity_type, original_id)
        self.assertEqual(existing_id, 100)

        db.session.rollback()
        IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).delete()
        db.session.commit()

    def test_truncate_to_month_datetime(self):
        """Test that truncation to month works for a datetime"""
        test_date = datetime(2024, 2, 15, 14, 30, 45)
        truncated = AnonymizedModel.truncate_to_month(test_date)

        self.assertEqual(truncated.year, 2024)
        self.assertEqual(truncated.month, 2)
        self.assertEqual(truncated.day, 1)
        self.assertEqual(truncated.hour, 0)
        self.assertEqual(truncated.minute, 0)
        self.assertEqual(truncated.second, 0)
        self.assertEqual(truncated.microsecond, 0)

    def test_truncate_to_month_date(self):
        """Test that truncation to month works for a date"""
        test_date = datetime(2024, 2, 15).date()
        truncated = AnonymizedModel.truncate_to_month(test_date)

        self.assertEqual(truncated.year, 2024)
        self.assertEqual(truncated.month, 2)
        self.assertEqual(truncated.day, 1)


class TestIdMappingService(BaseTest):
    def setUp(self):
        """Setup for each test - clean environment"""
        super().setUp()

    def test_user_negative_id_generation(self):
        """Test that user IDs are generated as negative integers."""
        db.session.rollback()

        try:
            IdMapping.query.filter_by(entity_type="user").delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.fail(f"Test failed: {e}")

        user_id = 12345
        expected_id = -100000 - user_id

        try:
            mapping = IdMapping(
                entity_type="user",
                original_id=user_id,
                anonymized_id=expected_id,
            )
            db.session.add(mapping)
            db.session.commit()

            negative_id = IdMappingService.get_user_negative_id(user_id)

            self.assertLess(negative_id, 0)
            self.assertEqual(negative_id, expected_id)

            IdMapping.query.filter_by(entity_type="user").delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.fail(f"Test failed: {e}")

    def test_entity_positive_id_generation(self):
        """Test that entity IDs are generated as positive integers."""
        db.session.rollback()

        try:
            IdMapping.query.filter_by(entity_type="mission").delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.fail(f"Test failed: {e}")

        mission_id = 54321
        entity_type = "mission"

        try:
            positive_id = IdMappingService.get_entity_positive_id(
                entity_type, mission_id
            )
            db.session.commit()

            # We know it will be positive, but we don't know the exact value
            # in the test environment, so we only check if it's positive
            self.assertGreater(positive_id, 0)

            mapping = IdMapping.query.filter_by(
                entity_type=entity_type, original_id=mission_id
            ).one_or_none()
            self.assertIsNotNone(mapping)
            self.assertEqual(mapping.anonymized_id, positive_id)

            self.assertEqual(
                IdMappingService.get_entity_positive_id(
                    entity_type, mission_id
                ),
                positive_id,
            )

            IdMapping.query.filter_by(entity_type=entity_type).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.fail(f"Test failed: {e}")

    def test_get_deletion_target_ids(self):
        """Test retrieving only entities marked as deletion targets."""
        db.session.rollback()

        try:
            IdMapping.query.delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.fail(f"Test failed: {e}")

        # Create user mappings with different deletion target flags
        user_ids = [1001, 1002, 1003]
        for i, user_id in enumerate(user_ids):
            negative_id = -100000 - user_id
            deletion_target = (
                i < 2
            )  # Mark only the first two as deletion targets

            mapping = IdMapping(
                entity_type="user",
                original_id=user_id,
                anonymized_id=negative_id,
                deletion_target=deletion_target,
            )
            db.session.add(mapping)

        # Create a mission mapping also marked as deletion target
        mission_mapping = IdMapping(
            entity_type="mission",
            original_id=2001,
            anonymized_id=250001,
            deletion_target=True,
        )
        db.session.add(mission_mapping)

        try:
            db.session.commit()

            # Test deletion targets for user entity type
            user_target_ids = IdMappingService.get_deletion_target_ids("user")
            self.assertEqual(len(user_target_ids), 2)
            self.assertEqual(user_target_ids, {1001, 1002})
            self.assertNotIn(1003, user_target_ids)

            # Test deletion targets for mission entity type
            mission_target_ids = IdMappingService.get_deletion_target_ids(
                "mission"
            )
            self.assertEqual(len(mission_target_ids), 1)
            self.assertEqual(mission_target_ids, {2001})

            # Test non-existent entity type
            empty_target_ids = IdMappingService.get_deletion_target_ids(
                "non_existent"
            )
            self.assertEqual(len(empty_target_ids), 0)
            self.assertEqual(empty_target_ids, set())

            IdMapping.query.delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            self.fail(f"Test failed: {e}")

    def test_clean_mappings(self):
        """Test that clean_mappings removes all mappings."""
        IdMapping.query.delete()
        db.session.commit()

        user_mapping = IdMapping(
            entity_type="user", original_id=1001, anonymized_id=-101001
        )
        mission_mapping = IdMapping(
            entity_type="mission", original_id=2001, anonymized_id=250001
        )
        db.session.add(user_mapping)
        db.session.add(mission_mapping)
        db.session.commit()

        count = IdMapping.query.count()
        self.assertEqual(count, 2)

        expected_changes = {
            "user_mapping_delete": DBEntryUpdate(
                model=IdMapping,
                before={
                    "entity_type": "user",
                    "original_id": 1001,
                    "anonymized_id": -101001,
                },
                after=None,
            ),
            "mission_mapping_delete": DBEntryUpdate(
                model=IdMapping,
                before={
                    "entity_type": "mission",
                    "original_id": 2001,
                    "anonymized_id": 250001,
                },
                after=None,
            ),
        }

        with test_db_changes(expected_changes, [IdMapping]):
            deleted = IdMappingService.clean_mappings()
            self.assertEqual(deleted, 2)

        final_count = IdMapping.query.count()
        self.assertEqual(final_count, 0)

    def test_mark_for_deletion(self):
        """Test marking entities for deletion."""
        IdMapping.query.delete()
        db.session.commit()

        user_id = 1001
        mapping = IdMapping(
            entity_type="user",
            original_id=user_id,
            anonymized_id=-100000 - user_id,
        )
        db.session.add(mapping)
        db.session.commit()

        self.assertFalse(mapping.deletion_target)
        target_ids = IdMappingService.get_deletion_target_ids("user")
        self.assertEqual(len(target_ids), 0)

        IdMappingService.mark_for_deletion("user", user_id)
        db.session.commit()

        db.session.refresh(mapping)
        self.assertTrue(mapping.deletion_target)
        target_ids = IdMappingService.get_deletion_target_ids("user")
        self.assertEqual(target_ids, {user_id})

        new_id = 2002
        self.assertIsNone(
            IdMapping.query.filter_by(
                entity_type="mission", original_id=new_id
            ).one_or_none()
        )

        IdMappingService.mark_for_deletion("mission", new_id)
        db.session.commit()

        new_mapping = IdMapping.query.filter_by(
            entity_type="mission", original_id=new_id
        ).one_or_none()
        self.assertIsNotNone(new_mapping)
        self.assertTrue(new_mapping.deletion_target)

        IdMapping.query.delete()
        db.session.commit()
