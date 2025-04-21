from app import db, app
from datetime import datetime, timedelta
from sqlalchemy import text

from app.models import User, Company, Employment, Mission, Activity, Vehicle
from app.models.user import UserAccountStatus
from app.models.anonymized import AnonActivity, AnonEmployment, IdMapping
from app.services.anonymization.user_related.user_anonymizer import (
    UserAnonymizer,
)
from app.services.anonymization.standalone.anonymization_executor import (
    AnonymizationExecutor,
)
from app.services.anonymization.id_mapping_service import IdMappingService
from app.seed.factories import CompanyFactory, UserFactory, EmploymentFactory
from app.seed.helpers import AuthenticatedUserContext
from app.tests import BaseTest


class TestAnonymizationReferences(BaseTest):
    """Test negative ID assignment and user references in anonymized tables."""

    def setUp(self):
        """Set up test data with application context."""
        self.app_context = app.app_context()
        self.app_context.push()

        super().setUp()
        self.company = CompanyFactory.create(
            usual_name="Test Company",
            siren="123456789",
        )

        # Create a user using factory
        self.user = UserFactory.create(
            email="test_user@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
            has_confirmed_email=True,
            has_activated_email=True,
        )

        # Create a second user for multi-user testing
        self.user2 = UserFactory.create(
            email="test_user2@example.com",
            password="password123",
            first_name="Second",
            last_name="User",
            has_confirmed_email=True,
            has_activated_email=True,
        )

        # Create an employment using factory
        self.employment = EmploymentFactory.create(
            user=self.user,
            company=self.company,
            start_date=datetime.now().date(),
            has_admin_rights=False,
            submitter=self.user,
            validation_status="approved",
            reception_time=datetime.now(),
        )

        # Create a mission and activity using authenticated context
        with AuthenticatedUserContext(user=self.user):
            # Create a mission
            self.mission = Mission(
                company=self.company,
                creation_time=datetime.now(),
                reception_time=datetime.now(),
                submitter=self.user,
            )
            db.session.add(self.mission)
            db.session.flush()

            # Create an activity
            current_time = datetime.now()
            self.activity = Activity(
                user=self.user,
                mission=self.mission,
                submitter=self.user,
                start_time=current_time - timedelta(hours=2),
                end_time=current_time - timedelta(hours=1),
                type="drive",
                reception_time=current_time,
                last_update_time=current_time,
            )
            db.session.add(self.activity)
            db.session.commit()

    def tearDown(self):
        """Clean up after test."""
        super().tearDown()
        self.app_context.pop()

    def test_user_negative_id_assignment(self):
        """Test that user anonymization creates user mappings with negative IDs."""
        # Anonymize the user - setting dry_run=False to actually modify the user
        anonymizer = UserAnonymizer(db.session, dry_run=False)
        anonymizer.anonymize_users_in_place({self.user.id})
        db.session.commit()

        # Verify user anonymization status
        user = User.query.get(self.user.id)
        self.assertEqual(
            user.status,
            UserAccountStatus.ANONYMIZED,
            "User should be marked as anonymized",
        )

        # Verify user ID hasn't changed
        self.assertEqual(
            user.id, self.user.id, "User ID should remain unchanged"
        )

        # Get the negative ID mapping for the user
        user_mapping = IdMapping.query.filter_by(
            entity_type="user", original_id=self.user.id
        ).one_or_none()

        self.assertIsNotNone(user_mapping, "User mapping should exist")
        negative_id = user_mapping.anonymized_id
        self.assertLess(
            negative_id, 0, msg="User mapping ID should be negative"
        )

        # Verify personal info is properly anonymized
        self.assertEqual(
            user.email,
            f"anon_{self.user.id}@anonymous.aa",
            "User email should use original ID",
        )
        self.assertEqual(
            user.first_name, "Anonymized", "First name should be anonymized"
        )
        self.assertEqual(
            user.last_name, "User", "Last name should be anonymized"
        )
        self.assertIsNone(user.phone_number, "Phone number should be removed")

        # Test IdMappingService.get_user_negative_id consistency
        retrieved_id = IdMappingService.get_user_negative_id(self.user.id)
        self.assertEqual(
            retrieved_id, negative_id, "ID retrieval should be consistent"
        )

    def test_multiple_user_anonymization(self):
        """Test negative ID mappings across multiple users."""
        # Anonymize multiple users
        anonymizer = UserAnonymizer(db.session, dry_run=False)
        anonymizer.anonymize_users_in_place({self.user.id, self.user2.id})
        db.session.commit()

        # Verify user IDs haven't changed
        user1 = User.query.get(self.user.id)
        user2 = User.query.get(self.user2.id)
        self.assertEqual(
            user1.id, self.user.id, "User 1 ID should remain unchanged"
        )
        self.assertEqual(
            user2.id, self.user2.id, "User 2 ID should remain unchanged"
        )

        # Get mappings
        user1_mapping = IdMapping.query.filter_by(
            entity_type="user", original_id=self.user.id
        ).one_or_none()
        user2_mapping = IdMapping.query.filter_by(
            entity_type="user", original_id=self.user2.id
        ).one_or_none()

        # Verify both mappings exist
        self.assertIsNotNone(user1_mapping, "User 1 mapping should exist")
        self.assertIsNotNone(user2_mapping, "User 2 mapping should exist")

        # Verify different negative IDs in mappings
        self.assertLess(
            user1_mapping.anonymized_id,
            0,
            msg="User 1 mapping should have negative ID",
        )
        self.assertLess(
            user2_mapping.anonymized_id,
            0,
            msg="User 2 mapping should have negative ID",
        )
        self.assertNotEqual(
            user1_mapping.anonymized_id,
            user2_mapping.anonymized_id,
            "Users should have different negative IDs in mappings",
        )

    def test_user_anonymization_then_entity_anonymization(self):
        """Test that references to previously anonymized users in newly anonymized entities use negative IDs from mappings."""
        # First anonymize the user (this doesn't change the user ID but creates a mapping)
        anonymizer = UserAnonymizer(db.session, dry_run=False)
        anonymizer.anonymize_users_in_place({self.user.id})
        db.session.commit()

        # Verify user ID hasn't changed
        user = User.query.get(self.user.id)
        self.assertEqual(
            user.id, self.user.id, "User ID should remain unchanged"
        )

        # Get user's negative ID from mapping
        user_mapping = IdMapping.query.filter_by(
            entity_type="user", original_id=self.user.id
        ).one_or_none()
        negative_id = user_mapping.anonymized_id

        # Then anonymize mission and activity data
        executor = AnonymizationExecutor(db.session, dry_run=False)
        executor.anonymize_mission_and_dependencies({self.mission.id})
        db.session.commit()

        # Verify that anonymized activity references the negative user ID from mapping
        anon_activities = AnonActivity.query.all()
        self.assertGreater(
            len(anon_activities), 0, msg="No anonymized activities found"
        )

        for activity in anon_activities:
            self.assertEqual(
                activity.user_id,
                negative_id,
                "User ID should be negative in anonymized activity (from mapping)",
            )
            self.assertEqual(
                activity.submitter_id,
                negative_id,
                "Submitter ID should be negative in anonymized activity (from mapping)",
            )

    def test_entity_anonymization_then_user_anonymization(self):
        """Test sequence: first anonymize entities, then anonymize users later."""
        # First anonymize mission and activity data
        executor = AnonymizationExecutor(db.session, dry_run=False)
        executor.anonymize_mission_and_dependencies({self.mission.id})
        db.session.commit()

        # Verify anonymized data exists
        anon_activities = AnonActivity.query.all()
        self.assertGreater(
            len(anon_activities), 0, msg="No anonymized activities found"
        )

        # Store original anonymized user IDs
        original_user_ids = [activity.user_id for activity in anon_activities]
        # User IDs should already be negative due to the get_new_id method in AnonymizedModel
        for original_id in original_user_ids:
            self.assertLess(
                original_id,
                0,
                "User IDs in anonymized activities should already be negative",
            )

        # Now anonymize the user (this won't change the user ID but creates a mapping)
        anonymizer = UserAnonymizer(db.session, dry_run=False)
        anonymizer.anonymize_users_in_place({self.user.id})
        db.session.commit()

        # Verify user ID hasn't changed
        user = User.query.get(self.user.id)
        self.assertEqual(
            user.id, self.user.id, "User ID should remain unchanged"
        )

        # Get user's negative ID from the mapping
        user_mapping = IdMapping.query.filter_by(
            entity_type="user", original_id=self.user.id
        ).one_or_none()
        negative_id = user_mapping.anonymized_id

        # Verify the mapping has a negative ID
        self.assertLess(
            negative_id,
            0,
            "User mapping should have a negative ID after anonymization",
        )

        # Refresh anonymized activities
        db.session.expire_all()
        anon_activities = AnonActivity.query.all()

        # Check if user references in anonymized entities remained the same
        for i, activity in enumerate(anon_activities):
            self.assertEqual(
                activity.user_id,
                original_user_ids[i],
                "References in existing anonymized records should remain unchanged",
            )

        # The negative IDs should be the same since both anonymization processes
        # use the same IdMappingService to generate negative IDs for users
        self.assertEqual(
            anon_activities[0].user_id,
            negative_id,
            "User IDs in anonymized activities should match the user's negative ID from mapping",
        )

    def test_employment_anonymization_with_negative_ids(self):
        """Test that anonymized employments reference users correctly."""
        # First anonymize the user (this won't change the user ID but creates a mapping)
        anonymizer = UserAnonymizer(db.session, dry_run=False)
        anonymizer.anonymize_users_in_place({self.user.id})
        db.session.commit()

        # Verify user ID hasn't changed
        user = User.query.get(self.user.id)
        self.assertEqual(
            user.id, self.user.id, "User ID should remain unchanged"
        )

        # Get user's negative ID from mapping
        user_mapping = IdMapping.query.filter_by(
            entity_type="user", original_id=self.user.id
        ).one_or_none()
        negative_id = user_mapping.anonymized_id

        # Anonymize employment
        executor = AnonymizationExecutor(db.session, dry_run=False)
        executor.anonymize_employment_and_dependencies({self.employment.id})
        db.session.commit()

        # Verify anonymized employment references the negative user ID from mapping
        anon_employments = AnonEmployment.query.all()
        self.assertGreater(
            len(anon_employments), 0, msg="No anonymized employments found"
        )

        for employment in anon_employments:
            self.assertEqual(
                employment.user_id,
                negative_id,
                "User ID should be negative in anonymized employment (from mapping)",
            )
            self.assertEqual(
                employment.submitter_id,
                negative_id,
                "Submitter ID should be negative in anonymized employment (from mapping)",
            )

    def test_mark_for_deletion_new_entity(self):
        """Test marking a new entity for deletion."""
        vehicle = Vehicle(
            registration_number="TEST-DEL-123",
            company_id=self.company.id,
            submitter_id=self.user.id,
        )
        db.session.add(vehicle)
        db.session.commit()

        mapping = IdMapping.query.filter_by(
            entity_type="vehicle", original_id=vehicle.id
        ).one_or_none()
        self.assertIsNone(mapping, "Should not have a mapping yet")

        # Mark for deletion
        IdMappingService.mark_for_deletion("vehicle", vehicle.id)
        db.session.commit()

        # Verify mapping was created with deletion_target=True
        mapping = IdMapping.query.filter_by(
            entity_type="vehicle", original_id=vehicle.id
        ).one_or_none()
        self.assertIsNotNone(mapping, "Mapping should exist now")
        self.assertTrue(
            mapping.deletion_target, "Should be marked for deletion"
        )

    def test_mark_for_deletion_existing_entity(self):
        """Test marking an existing entity for deletion."""
        vehicle = Vehicle(
            registration_number="TEST-EXIST-123",
            company_id=self.company.id,
            submitter_id=self.user.id,
        )
        db.session.add(vehicle)
        db.session.commit()

        # Create a mapping without marking for deletion
        IdMappingService.get_entity_positive_id("vehicle", vehicle.id)
        db.session.commit()

        # Verify mapping exists but not marked for deletion
        mapping = IdMapping.query.filter_by(
            entity_type="vehicle", original_id=vehicle.id
        ).one_or_none()
        self.assertIsNotNone(mapping, "Mapping should exist")
        self.assertFalse(
            mapping.deletion_target, "Should not be marked for deletion yet"
        )

        # Now mark for deletion
        IdMappingService.mark_for_deletion("vehicle", vehicle.id)
        db.session.commit()

        # Verify mapping is now marked for deletion
        mapping = IdMapping.query.filter_by(
            entity_type="vehicle", original_id=vehicle.id
        ).one_or_none()
        self.assertTrue(
            mapping.deletion_target, "Should now be marked for deletion"
        )

    def test_get_deletion_target_ids(self):
        """Test retrieving only entities marked for deletion."""
        # Create multiple vehicles with different deletion states
        vehicle1 = Vehicle(
            registration_number="TEST-DEL-1",
            company_id=self.company.id,
            submitter_id=self.user.id,
        )
        vehicle2 = Vehicle(
            registration_number="TEST-DEL-2",
            company_id=self.company.id,
            submitter_id=self.user.id,
        )
        vehicle3 = Vehicle(
            registration_number="TEST-DEL-3",
            company_id=self.company.id,
            submitter_id=self.user.id,
        )
        db.session.add_all([vehicle1, vehicle2, vehicle3])
        db.session.commit()

        # Create mappings for all vehicles
        IdMappingService.get_entity_positive_id("vehicle", vehicle1.id)
        IdMappingService.get_entity_positive_id("vehicle", vehicle2.id)
        IdMappingService.get_entity_positive_id("vehicle", vehicle3.id)

        # Mark only vehicles 1 and 3 for deletion
        IdMappingService.mark_for_deletion("vehicle", vehicle1.id)
        IdMappingService.mark_for_deletion("vehicle", vehicle3.id)
        db.session.commit()

        # Get deletion targets
        targets = IdMappingService.get_deletion_target_ids("vehicle")

        # Verify only vehicles 1 and 3 are in the targets
        self.assertEqual(len(targets), 2, "Should have 2 deletion targets")
        self.assertIn(
            vehicle1.id, targets, "Vehicle 1 should be marked for deletion"
        )
        self.assertNotIn(
            vehicle2.id, targets, "Vehicle 2 should not be marked for deletion"
        )
        self.assertIn(
            vehicle3.id, targets, "Vehicle 3 should be marked for deletion"
        )
