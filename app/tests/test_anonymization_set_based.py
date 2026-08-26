from datetime import datetime, timedelta

from app import app, db
from app.models import (
    Activity,
    ActivityVersion,
    Address,
    Mission,
    MissionEnd,
    MissionValidation,
)
from app.models.location_entry import LocationEntry, LocationEntryType
from app.models.anonymized import (
    AnonActivity,
    AnonActivityVersion,
    AnonLocationEntry,
    AnonMission,
    AnonMissionEnd,
    AnonMissionValidation,
    IdMapping,
)
from app.services.anonymization.standalone.anonymization_executor import (
    ANON_TABLE_COLUMNS,
    AnonymizationExecutor,
)
from app.seed.factories import CompanyFactory, EmploymentFactory, UserFactory
from app.seed.helpers import AuthenticatedUserContext
from app.tests import BaseTest


class TestSetBasedCopies(BaseTest):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        super().setUp()

        self.company = CompanyFactory.create(
            usual_name="Set Based Co", siren="987654321"
        )
        self.worker = UserFactory.create(email="worker@example.com")
        self.admin = UserFactory.create(email="admin@example.com")
        EmploymentFactory.create(
            user=self.worker,
            company=self.company,
            start_date=datetime.now().date(),
            has_admin_rights=False,
            submitter=self.worker,
            validation_status="approved",
            reception_time=datetime.now(),
        )

        self.now = datetime(2022, 3, 15, 14, 30, 45)
        with AuthenticatedUserContext(user=self.worker):
            self.mission = Mission(
                company=self.company,
                creation_time=self.now,
                reception_time=self.now,
                submitter=self.worker,
            )
            db.session.add(self.mission)
            db.session.flush()

            self.ended_activity = Activity(
                user=self.worker,
                mission=self.mission,
                submitter=self.worker,
                start_time=self.now - timedelta(hours=3),
                end_time=self.now - timedelta(hours=1),
                type="drive",
                reception_time=self.now,
                last_update_time=self.now,
            )
            self.ongoing_activity = Activity(
                user=self.worker,
                mission=self.mission,
                submitter=self.worker,
                start_time=self.now - timedelta(hours=1),
                end_time=None,
                type="work",
                reception_time=self.now,
                last_update_time=self.now,
            )
            db.session.add_all([self.ended_activity, self.ongoing_activity])

            db.session.add(
                MissionEnd(
                    submitter=self.worker,
                    reception_time=self.now,
                    user=self.worker,
                    mission=self.mission,
                )
            )
            # admin validation without target user: nullable user_id path
            db.session.add(
                MissionValidation(
                    submitter=self.admin,
                    mission=self.mission,
                    user=None,
                    reception_time=self.now,
                    is_admin=True,
                    is_auto=False,
                )
            )
            # auto validation has no submitter: NULL-submitter skip path
            db.session.add(
                MissionValidation(
                    submitter=None,
                    mission=self.mission,
                    user=self.worker,
                    reception_time=self.now,
                    is_admin=True,
                    is_auto=True,
                )
            )

            self.address = Address(name="1 rue de la Paix", manual=True)
            db.session.add(self.address)
            db.session.flush()
            db.session.add(
                LocationEntry(
                    mission_id=self.mission.id,
                    address_id=self.address.id,
                    type=LocationEntryType.MISSION_START_LOCATION,
                    reception_time=self.now,
                    submitter_id=self.worker.id,
                )
            )
            db.session.commit()

    def tearDown(self):
        super().tearDown()
        self.app_context.pop()

    def anonymize_mission(self):
        executor = AnonymizationExecutor(db.session, dry_run=True)
        executor.anonymize_mission_and_dependencies({self.mission.id})
        db.session.commit()

    def get_mapping(self, entity_type, original_id):
        return IdMapping.query.filter_by(
            entity_type=entity_type, original_id=original_id
        ).one()

    def test_full_subtree_copied_with_remapped_references(self):
        source_version_count = ActivityVersion.query.count()

        self.anonymize_mission()

        mission_mapping = self.get_mapping("mission", self.mission.id)
        anon_mission = AnonMission.query.get(mission_mapping.anonymized_id)
        self.assertIsNotNone(anon_mission)

        worker_mapping = self.get_mapping("user", self.worker.id)
        self.assertLess(worker_mapping.anonymized_id, 0)
        company_mapping = self.get_mapping("company", self.company.id)
        self.assertEqual(
            anon_mission.company_id, company_mapping.anonymized_id
        )
        self.assertEqual(
            anon_mission.submitter_id, worker_mapping.anonymized_id
        )

        anon_activities = AnonActivity.query.all()
        self.assertEqual(len(anon_activities), 2)
        for anon_activity in anon_activities:
            self.assertEqual(anon_activity.mission_id, anon_mission.id)
            self.assertEqual(
                anon_activity.user_id, worker_mapping.anonymized_id
            )

        self.assertEqual(
            AnonActivityVersion.query.count(), source_version_count
        )
        self.assertEqual(AnonMissionEnd.query.count(), 1)
        self.assertEqual(AnonLocationEntry.query.count(), 1)

        anon_entry = AnonLocationEntry.query.one()
        address_mapping = self.get_mapping("address", self.address.id)
        self.assertEqual(anon_entry.address_id, address_mapping.anonymized_id)
        self.assertIsNone(anon_entry.company_known_address_id)

    def test_dates_truncated_and_durations_preserved(self):
        self.anonymize_mission()

        mission_mapping = self.get_mapping("mission", self.mission.id)
        anon_mission = AnonMission.query.get(mission_mapping.anonymized_id)
        self.assertEqual(anon_mission.creation_time, datetime(2022, 3, 1))

        ended_mapping = self.get_mapping("activity", self.ended_activity.id)
        anon_ended = AnonActivity.query.get(ended_mapping.anonymized_id)
        self.assertEqual(anon_ended.start_time, datetime(2022, 3, 1))
        self.assertEqual(
            anon_ended.end_time - anon_ended.start_time, timedelta(hours=2)
        )

        ongoing_mapping = self.get_mapping(
            "activity", self.ongoing_activity.id
        )
        anon_ongoing = AnonActivity.query.get(ongoing_mapping.anonymized_id)
        self.assertIsNone(anon_ongoing.end_time)

    def test_validation_nullable_user_and_null_submitter_skip(self):
        self.anonymize_mission()

        self.assertEqual(AnonMissionValidation.query.count(), 1)
        anon_validation = AnonMissionValidation.query.one()
        admin_mapping = self.get_mapping("user", self.admin.id)
        self.assertEqual(
            anon_validation.submitter_id, admin_mapping.anonymized_id
        )
        self.assertIsNone(anon_validation.user_id)

    def test_insert_column_lists_match_anon_models(self):
        for table, columns in ANON_TABLE_COLUMNS.items():
            self.assertCountEqual(
                columns, db.metadata.tables[table].columns.keys(), table
            )

    def test_null_submitter_check_rejects_unknown_table(self):
        executor = AnonymizationExecutor(db.session, dry_run=True)
        with self.assertRaises(ValueError):
            executor.warn_skipped_null_submitters(
                "mission; DROP TABLE mission", {self.mission.id}
            )

    def test_reconciliation_warns_on_skipped_rows(self):
        self.anonymize_mission()

        # second run: ON CONFLICT skips every row, the delta must be logged
        with self.assertLogs(
            "app.services.anonymization.standalone.anonymization_executor",
            level="WARNING",
        ) as logs:
            self.anonymize_mission()
        self.assertTrue(
            any("not copied" in message for message in logs.output)
        )

    def test_copies_are_idempotent(self):
        self.anonymize_mission()

        counts_before = (
            AnonMission.query.count(),
            AnonActivity.query.count(),
            AnonActivityVersion.query.count(),
            AnonMissionEnd.query.count(),
            AnonMissionValidation.query.count(),
            AnonLocationEntry.query.count(),
            IdMapping.query.count(),
        )

        self.anonymize_mission()

        counts_after = (
            AnonMission.query.count(),
            AnonActivity.query.count(),
            AnonActivityVersion.query.count(),
            AnonMissionEnd.query.count(),
            AnonMissionValidation.query.count(),
            AnonLocationEntry.query.count(),
            IdMapping.query.count(),
        )
        self.assertEqual(counts_before, counts_after)
