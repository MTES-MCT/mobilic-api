from datetime import datetime, timedelta
from unittest.mock import patch

from app import app, db
from app.helpers.notification_type import NotificationType
from app.models import (
    Activity,
    CompanyCertification,
    Mission,
    MissionAutoValidation,
)
from app.models.export import Export, ExportType, ExportStatus
from app.models.notification import Notification
from app.models.scenario_testing import Action, Scenario, ScenarioTesting
from app.models.totp_credential import TotpCredential
from app.models.user import UserAccountStatus
from app.models.anonymized import (
    AnonActivity,
    AnonCompanyCertification,
    AnonMission,
    IdMapping,
)
from app.services.anonymization import anonymize_expired_data
from app.services.anonymization.user_related import anonymize_users
from app.services.anonymization.id_mapping_service import IdMappingService
from app.services.anonymization.standalone.anonymization_executor import (
    AnonymizationExecutor,
)
from app.services.anonymization.standalone.data_finder import DataFinder
from app.seed.factories import CompanyFactory, EmploymentFactory, UserFactory
from app.seed.helpers import AuthenticatedUserContext
from app.tests import BaseTest


class TestAnonymizationBatching(BaseTest):
    MISSION_COUNT = 5

    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        super().setUp()

        self.company = CompanyFactory.create(
            usual_name="Batch Co", siren="123123123"
        )
        self.worker = UserFactory.create(email="batch_worker@example.com")
        EmploymentFactory.create(
            user=self.worker,
            company=self.company,
            start_date=datetime.now().date(),
            has_admin_rights=False,
            submitter=self.worker,
            validation_status="approved",
            reception_time=datetime.now(),
        )

        self.mission_ids = []
        base_time = datetime(2022, 1, 10, 8, 0, 0)
        with AuthenticatedUserContext(user=self.worker):
            for i in range(self.MISSION_COUNT):
                mission_time = base_time + timedelta(days=i)
                mission = Mission(
                    company=self.company,
                    creation_time=mission_time,
                    reception_time=mission_time,
                    submitter=self.worker,
                )
                db.session.add(mission)
                db.session.flush()
                db.session.add(
                    Activity(
                        user=self.worker,
                        mission=mission,
                        submitter=self.worker,
                        start_time=mission_time,
                        end_time=mission_time + timedelta(hours=2),
                        type="drive",
                        reception_time=mission_time,
                        last_update_time=mission_time + timedelta(hours=2),
                    )
                )
                self.mission_ids.append(mission.id)
            db.session.commit()

        self.cutoff = datetime.now() - timedelta(minutes=5)

    def tearDown(self):
        super().tearDown()
        self.app_context.pop()

    def test_mission_cap_limits_each_run(self):
        with patch.dict(app.config, {"ANONYMIZATION_MAX_MISSIONS_PER_RUN": 3}):
            DataFinder(db.session, dry_run=True).anonymize_standalone_data(
                self.cutoff
            )

        marked = IdMappingService.get_deletion_target_ids("mission")
        self.assertEqual(marked, set(sorted(self.mission_ids)[:3]))
        self.assertEqual(AnonMission.query.count(), 3)

    def test_inactive_company_missions_bypass_the_cap(self):
        inactive_company = CompanyFactory.create(
            usual_name="Old Co", siren="321321321"
        )
        inactive_company.creation_time = datetime(2022, 1, 1)
        db.session.commit()

        company_mission_ids = []
        with AuthenticatedUserContext(user=self.worker):
            for i in range(3):
                mission_time = datetime(2022, 6, 1 + i)
                mission = Mission(
                    company=inactive_company,
                    creation_time=mission_time,
                    reception_time=mission_time,
                    submitter=self.worker,
                )
                db.session.add(mission)
                db.session.flush()
                company_mission_ids.append(mission.id)
            db.session.commit()

        with patch.dict(app.config, {"ANONYMIZATION_MAX_MISSIONS_PER_RUN": 2}):
            DataFinder(db.session, dry_run=True).anonymize_standalone_data(
                self.cutoff
            )

        marked = IdMappingService.get_deletion_target_ids("mission")
        self.assertTrue(set(company_mission_ids).issubset(marked))
        self.assertEqual(len(marked), 5)
        self.assertEqual(
            IdMappingService.get_deletion_target_ids("company"),
            {inactive_company.id},
        )

    def test_user_phase_skipped_when_cap_reached(self):
        anonymized_user = UserFactory.create(email="anon_user@example.com")
        anonymized_user.status = UserAccountStatus.ANONYMIZED
        anonymized_user.creation_time = datetime(2022, 1, 1)
        db.session.commit()
        user_id = anonymized_user.id

        with patch.dict(app.config, {"ANONYMIZATION_MAX_MISSIONS_PER_RUN": 2}):
            DataFinder(db.session, dry_run=True).anonymize_standalone_data(
                self.cutoff
            )
        self.assertEqual(
            IdMappingService.get_deletion_target_ids("user"), set()
        )

        DataFinder(db.session, dry_run=True).anonymize_standalone_data(
            self.cutoff
        )
        self.assertEqual(
            IdMappingService.get_deletion_target_ids("user"), {user_id}
        )

    def test_interrupted_run_keeps_committed_batches_and_resumes(self):
        finder = DataFinder(db.session, dry_run=True)
        original = finder.anonymize_mission_and_dependencies
        calls = {"count": 0}

        def failing_batch(mission_ids):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("simulated kill")
            return original(mission_ids)

        finder.anonymize_mission_and_dependencies = failing_batch

        with patch(
            "app.services.anonymization.standalone.data_finder"
            ".MISSION_BATCH_SIZE",
            2,
        ):
            with self.assertRaises(RuntimeError):
                finder.anonymize_standalone_data(self.cutoff)

            marked_after_crash = IdMappingService.get_deletion_target_ids(
                "mission"
            )
            self.assertEqual(
                marked_after_crash, set(sorted(self.mission_ids)[:2])
            )
            self.assertEqual(AnonMission.query.count(), 2)
            anon_ids_after_crash = {m.id for m in AnonMission.query.all()}

            DataFinder(db.session, dry_run=True).anonymize_standalone_data(
                self.cutoff
            )

        self.assertEqual(
            IdMappingService.get_deletion_target_ids("mission"),
            set(self.mission_ids),
        )
        self.assertEqual(AnonMission.query.count(), self.MISSION_COUNT)
        self.assertTrue(
            anon_ids_after_crash.issubset(
                {m.id for m in AnonMission.query.all()}
            )
        )
        self.assertEqual(
            IdMapping.query.filter_by(entity_type="mission").count(),
            self.MISSION_COUNT,
        )

    def test_user_dependencies_added_since_pipeline_creation_are_deleted(
        self,
    ):
        pending = UserFactory.create(email="pending_anon@example.com")
        pending.status = UserAccountStatus.ANONYMIZED
        pending.creation_time = datetime(2022, 1, 1)

        db.session.add(
            Notification(
                user=pending,
                type=NotificationType.MISSION_AUTO_VALIDATION,
                data=None,
            )
        )
        db.session.add(
            Export(
                user=pending,
                export_type=ExportType.EXCEL,
                status=ExportStatus.READY,
            )
        )
        db.session.add(
            ScenarioTesting(
                user=pending,
                scenario=Scenario.SCENARIO_A,
                action=Action.LOAD,
            )
        )
        db.session.add(
            TotpCredential(
                owner_type="user",
                owner_id=pending.id,
                secret="dummy-secret",
                enabled=True,
            )
        )
        db.session.commit()
        pending_id = pending.id

        anonymize_users(dry_run=False)
        AnonymizationExecutor(
            db.session, dry_run=False
        ).delete_user_dependencies({pending_id})
        db.session.commit()

        db.session.expire_all()
        self.assertEqual(
            Notification.query.filter_by(user_id=pending_id).count(), 0
        )
        self.assertEqual(Export.query.filter_by(user_id=pending_id).count(), 0)
        self.assertEqual(
            ScenarioTesting.query.filter_by(user_id=pending_id).count(), 0
        )
        self.assertEqual(
            TotpCredential.query.filter_by(
                owner_type="user", owner_id=pending_id
            ).count(),
            0,
        )

    def test_company_certification_is_copied_with_source_columns(self):
        old_company = CompanyFactory.create(
            usual_name="Certified Old Co", siren="999888777"
        )
        old_company.creation_time = datetime(2021, 1, 1)

        cert = CompanyCertification(
            company=old_company,
            attribution_date=datetime(2021, 2, 1).date(),
            expiration_date=datetime(2021, 4, 1).date(),
            log_in_real_time=0.72,
            admin_changes=0.18,
            compliancy=3,
        )
        db.session.add(cert)
        db.session.commit()

        anonymize_expired_data(dry_run=True)

        anon_certs = AnonCompanyCertification.query.all()
        self.assertEqual(len(anon_certs), 1)
        anon = anon_certs[0]
        self.assertAlmostEqual(anon.log_in_real_time, 0.72, places=4)
        self.assertAlmostEqual(anon.admin_changes, 0.18, places=4)
        self.assertEqual(anon.compliancy, 3)
        # certification_level_int is populated by the before_insert event
        self.assertIsNotNone(anon.certification_level_int)

    def test_test_mode_leaves_no_trace(self):
        DataFinder(db.session, dry_run=True).anonymize_standalone_data(
            self.cutoff, test_mode=True
        )

        self.assertEqual(IdMapping.query.count(), 0)
        self.assertEqual(AnonMission.query.count(), 0)
        self.assertEqual(AnonActivity.query.count(), 0)
        self.assertEqual(Mission.query.count(), self.MISSION_COUNT)

    def test_delete_phase_batches_and_completes(self):
        DataFinder(db.session, dry_run=True).anonymize_standalone_data(
            self.cutoff
        )
        self.assertEqual(Mission.query.count(), self.MISSION_COUNT)

        with patch(
            "app.services.anonymization.standalone.data_finder"
            ".MISSION_BATCH_SIZE",
            2,
        ):
            DataFinder(db.session, dry_run=False).delete_anonymized_data(
                self.cutoff
            )

        self.assertEqual(Mission.query.count(), 0)
        self.assertEqual(Activity.query.count(), 0)
        # Anonymized copies and mappings survive the delete phase
        # (mapping cleanup is handled at manager level)
        self.assertEqual(AnonMission.query.count(), self.MISSION_COUNT)
        self.assertEqual(
            IdMapping.query.filter_by(entity_type="mission").count(),
            self.MISSION_COUNT,
        )

    def test_cron_like_two_phase_pipeline(self):
        with AuthenticatedUserContext(user=self.worker):
            db.session.add(
                MissionAutoValidation(
                    mission_id=self.mission_ids[0],
                    user=self.worker,
                    is_admin=False,
                    reception_time=datetime.now(),
                )
            )
            db.session.commit()

        anonymize_expired_data(dry_run=True)

        self.assertEqual(AnonMission.query.count(), self.MISSION_COUNT)
        self.assertEqual(Mission.query.count(), self.MISSION_COUNT)
        self.assertGreater(IdMapping.query.count(), 0)

        # a second copy run must resume on leftover mappings, not refuse
        # nor duplicate anything
        anonymize_expired_data(dry_run=True)
        self.assertEqual(AnonMission.query.count(), self.MISSION_COUNT)

        # the nightly user step must not wipe the resume state either
        anonymize_users(dry_run=False)
        self.assertGreater(IdMapping.query.count(), 0)

        # neither must a --test run: it rolls back its own writes, so
        # cleaning would only ever delete a previous run's resume state
        mappings_before_test = IdMapping.query.count()
        anonymize_expired_data(dry_run=True, test_mode=True)
        self.assertEqual(IdMapping.query.count(), mappings_before_test)

        anonymize_expired_data(delete_only=True)

        self.assertEqual(Mission.query.count(), 0)
        self.assertEqual(Activity.query.count(), 0)
        self.assertEqual(MissionAutoValidation.query.count(), 0)
        self.assertEqual(AnonMission.query.count(), self.MISSION_COUNT)
        self.assertEqual(AnonActivity.query.count(), self.MISSION_COUNT)
        # complete delete-only run cleans the mapping table
        self.assertEqual(IdMapping.query.count(), 0)
