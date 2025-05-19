from app import db
from datetime import date
from unittest import mock

from app.models.anonymized.id_mapping import IdMapping
from app.services.anonymization.id_mapping_service import IdMappingService
from app.tests import BaseTest


class TestDeletionTarget(BaseTest):
    """Tests for deletion target functionality in id_mapping_service."""

    def setUp(self):
        """Set up test data with a clean ID mapping table."""
        super().setUp()
        # Clean up before test
        IdMapping.query.delete()
        db.session.commit()

    def tearDown(self):
        """Clean up after test."""
        IdMapping.query.delete()
        db.session.commit()
        super().tearDown()

    def test_mark_for_deletion(self):
        """Test marking entities for deletion."""
        # Create mapping for an entity without marking it for deletion
        entity_type = "test_entity"
        entity_id = 12345

        # First create a normal mapping without marking for deletion
        IdMappingService.get_entity_positive_id(entity_type, entity_id)
        db.session.commit()

        # Verify mapping exists but is not marked for deletion
        mapping = IdMapping.query.filter_by(
            entity_type=entity_type, original_id=entity_id
        ).one_or_none()

        self.assertIsNotNone(mapping, "Mapping should exist")
        self.assertFalse(
            mapping.deletion_target,
            "Should not be marked for deletion initially",
        )

        # Now mark it for deletion
        IdMappingService.mark_for_deletion(entity_type, entity_id)
        db.session.commit()

        # Verify it's now marked for deletion
        db.session.refresh(mapping)
        self.assertTrue(
            mapping.deletion_target, "Should now be marked for deletion"
        )

    def test_get_deletion_target_ids(self):
        """Test retrieving IDs of entities marked for deletion."""
        entity_type = "test_entity"

        # Create multiple mappings with different deletion states
        # Create odd-numbered IDs (1,3,5) that will be marked for deletion
        # Create even-numbered IDs (2,4) that won't be marked
        for i in range(1, 6):
            IdMappingService.get_entity_positive_id(entity_type, i)
            if i % 2 == 1:  # Only mark odd numbers for deletion
                IdMappingService.mark_for_deletion(entity_type, i)

        db.session.commit()

        # Get deletion targets
        deletion_targets = IdMappingService.get_deletion_target_ids(
            entity_type
        )

        # Verify only odd numbers are in deletion targets
        self.assertEqual(
            len(deletion_targets), 3, "Should have 3 deletion targets"
        )
        self.assertIn(
            1, deletion_targets, "ID 1 should be marked for deletion"
        )
        self.assertIn(
            3, deletion_targets, "ID 3 should be marked for deletion"
        )
        self.assertIn(
            5, deletion_targets, "ID 5 should be marked for deletion"
        )
        self.assertNotIn(
            2, deletion_targets, "ID 2 should not be marked for deletion"
        )
        self.assertNotIn(
            4, deletion_targets, "ID 4 should not be marked for deletion"
        )

    def test_mark_new_entity_for_deletion(self):
        """Test marking a new, previously unknown entity for deletion."""
        entity_type = "test_entity"
        entity_id = 9999

        # Verify entity doesn't have a mapping yet
        self.assertIsNone(
            IdMapping.query.filter_by(
                entity_type=entity_type, original_id=entity_id
            ).one_or_none(),
            "Should not have mapping before test",
        )

        # Mark for deletion directly without first creating a regular mapping
        IdMappingService.mark_for_deletion(entity_type, entity_id)
        db.session.commit()

        # Verify mapping was created and marked for deletion
        mapping = IdMapping.query.filter_by(
            entity_type=entity_type, original_id=entity_id
        ).one_or_none()

        self.assertIsNotNone(mapping, "Mapping should have been created")
        self.assertTrue(
            mapping.deletion_target, "Should be marked for deletion"
        )
        self.assertGreater(
            mapping.anonymized_id, 0, "Should have a positive anonymized ID"
        )
