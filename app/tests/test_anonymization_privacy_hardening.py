from datetime import datetime, timedelta

from app import app, db
from app.models import (
    Activity,
    Mission,
)
from app.models.anonymized import (
    AnonActivity,
    AnonCompany,
    AnonEmployment,
    AnonMissionValidation,
    AnonRegulationComputation,
    AnonRegulatoryAlert,
    AnonControllerControl,
    IdMapping,
)
from app.models.anonymized.base import AnonymizedModel
from app.models.anonymized.regulatory_alert import _scrub_extra_datetimes
from app.models.anonymized.controller_control import (
    _scrub_observed_infractions,
)
from app.services.anonymization.id_mapping_service import IdMappingService
from app.services.anonymization.utilities.k_anonymity import (
    apply_activity_k_anonymity,
)
from app.services.anonymization.standalone.anonymization_executor import (
    AnonymizationExecutor,
)
from app.seed.factories import CompanyFactory, EmploymentFactory, UserFactory
from app.seed.helpers import AuthenticatedUserContext
from app.tests import BaseTest


class TestAnonymizationPrivacyHardening(BaseTest):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        super().setUp()

        self.company = CompanyFactory.create(
            usual_name="Privacy Co", siren="555111222"
        )
        self.worker = UserFactory.create(email="priv_worker@example.com")
        EmploymentFactory.create(
            user=self.worker,
            company=self.company,
            start_date=datetime.now().date(),
            has_admin_rights=False,
            submitter=self.worker,
            validation_status="approved",
            reception_time=datetime.now(),
        )

    def tearDown(self):
        super().tearDown()
        self.app_context.pop()

    def test_bucket_end_time_rounds_to_30_min(self):
        start = datetime(2024, 1, 1, 8, 0, 0)
        self.assertEqual(
            AnonymizedModel.bucket_end_time(
                start, start + timedelta(minutes=17)
            ),
            start + timedelta(minutes=30),
        )
        self.assertEqual(
            AnonymizedModel.bucket_end_time(
                start, start + timedelta(minutes=44)
            ),
            start + timedelta(minutes=30),
        )
        self.assertEqual(
            AnonymizedModel.bucket_end_time(
                start, start + timedelta(minutes=46)
            ),
            start + timedelta(hours=1),
        )
        # 1s must not round to 0: sub-bucket spans still count as one bucket
        self.assertEqual(
            AnonymizedModel.bucket_end_time(
                start, start + timedelta(seconds=1)
            ),
            start + timedelta(minutes=30),
        )
        self.assertEqual(
            AnonymizedModel.bucket_end_time(start, start),
            start,
        )
        self.assertIsNone(AnonymizedModel.bucket_end_time(start, None))
        self.assertIsNone(AnonymizedModel.bucket_end_time(None, start))

    def test_activity_end_time_is_bucketed_by_set_based_copy(self):
        base = datetime(2022, 4, 10, 8, 0, 0)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission(
                company=self.company,
                creation_time=base,
                reception_time=base,
                submitter=self.worker,
            )
            db.session.add(mission)
            db.session.flush()
            db.session.add(
                Activity(
                    user=self.worker,
                    mission=mission,
                    submitter=self.worker,
                    start_time=base,
                    end_time=base + timedelta(minutes=17),
                    type="drive",
                    reception_time=base,
                    last_update_time=base + timedelta(minutes=17),
                )
            )
            db.session.commit()
            mission_id = mission.id

        executor = AnonymizationExecutor(db.session, dry_run=True)
        executor.anonymize_mission_and_dependencies({mission_id})
        db.session.commit()

        anon = AnonActivity.query.one()
        self.assertEqual(
            anon.end_time - anon.start_time, timedelta(minutes=30)
        )

    def test_scrub_extra_datetimes_trims_iso_to_month(self):
        cleaned = _scrub_extra_datetimes(
            {
                "sanction_code": "NATINF-1234",
                "breach_period_start": "2024-03-15T09:22:41+00:00",
                "breach_period_end": "2024-03-15T10:22:41+00:00",
                "work_range_start": "2024-03-14T05:00:00",
                "unknown_key": "keep me",
            }
        )
        self.assertEqual(cleaned["sanction_code"], "NATINF-1234")
        self.assertEqual(cleaned["unknown_key"], "keep me")
        self.assertTrue(
            cleaned["breach_period_start"].startswith("2024-03-01")
        )
        self.assertTrue(cleaned["breach_period_end"].startswith("2024-03-01"))
        self.assertTrue(cleaned["work_range_start"].startswith("2024-03-01"))

    def test_scrub_observed_infractions_trims_dates_and_nested_extra(self):
        cleaned = _scrub_observed_infractions(
            [
                {
                    "sanction": "NATINF-42",
                    "date": "2024-05-17",
                    "extra": {
                        "breach_period_start": "2024-05-17T04:00:00+00:00",
                    },
                }
            ]
        )
        self.assertEqual(cleaned[0]["date"], "2024-05-01")
        self.assertTrue(
            cleaned[0]["extra"]["breach_period_start"].startswith("2024-05-01")
        )

    def test_regulation_computation_day_is_truncated_to_month(self):
        from app.models.regulation_computation import RegulationComputation
        from app.helpers.submitter_type import SubmitterType

        IdMappingService.get_user_negative_id(self.worker.id)
        original = RegulationComputation(
            user=self.worker,
            day=datetime(2024, 6, 17).date(),
            submitter_type=SubmitterType.EMPLOYEE,
            creation_time=datetime(2024, 6, 17, 8, 0, 0),
        )
        db.session.add(original)
        db.session.commit()

        anon = AnonRegulationComputation.anonymize(original)
        self.assertEqual(anon.day, datetime(2024, 6, 1).date())

    def test_anon_company_business_id_is_remapped(self):
        anon = AnonCompany.anonymize(self.company)
        db.session.commit()
        if self.company.business_id is not None:
            mapping = IdMapping.query.filter_by(
                entity_type="business", original_id=self.company.business_id
            ).one()
            self.assertEqual(anon.business_id, mapping.anonymized_id)
        else:
            self.assertIsNone(anon.business_id)

    def test_dropped_columns_are_gone(self):
        self.assertNotIn("is_admin", AnonMissionValidation.__table__.columns)
        self.assertNotIn("has_admin_rights", AnonEmployment.__table__.columns)
        self.assertNotIn(
            "regulation_check_id", AnonRegulatoryAlert.__table__.columns
        )

    def test_user_creation_time_is_truncated_to_month(self):
        from app.services.anonymization.user_related.user_anonymizer import (
            UserAnonymizer,
        )

        self.worker.creation_time = datetime(2020, 5, 17, 14, 22, 11)
        db.session.commit()
        anonymizer = UserAnonymizer(db.session, dry_run=False)
        anonymizer.anonymize_users_in_place({self.worker.id})
        db.session.commit()

        db.session.refresh(self.worker)
        self.assertEqual(
            self.worker.creation_time.replace(tzinfo=None),
            datetime(2020, 5, 1, 0, 0, 0),
        )

    def test_k_anonymity_drops_users_with_unique_activity_count(self):
        base = datetime(2024, 1, 1)
        db.session.execute(AnonActivity.__table__.delete())
        rows = []
        for uid, count in [
            (-11, 2),
            (-12, 2),
            (-13, 2),
            (-14, 5),
        ]:
            for i in range(count):
                rows.append(
                    {
                        "id": abs(uid) * 100 + i,
                        "type": "drive",
                        "user_id": uid,
                        "submitter_id": uid,
                        "mission_id": abs(uid),
                        "creation_time": base,
                        "start_time": base,
                        "end_time": base + timedelta(minutes=30),
                        "last_update_time": base,
                    }
                )
        db.session.execute(AnonActivity.__table__.insert(), rows)
        db.session.commit()

        deleted = apply_activity_k_anonymity(k=2)

        self.assertEqual(deleted, 5)
        remaining_user_ids = {
            r[0]
            for r in db.session.query(AnonActivity.user_id).distinct().all()
        }
        self.assertEqual(remaining_user_ids, {-11, -12, -13})
