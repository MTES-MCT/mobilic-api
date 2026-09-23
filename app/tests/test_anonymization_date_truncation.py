from datetime import datetime, timedelta

from app import app, db
from app.models.anonymized import AnonRegulationComputation
from app.models.anonymized.base import AnonymizedModel
from app.models.anonymized.regulatory_alert import _scrub_extra_datetimes
from app.models.anonymized.controller_control import (
    _scrub_observed_infractions,
)
from app.services.anonymization.id_mapping_service import IdMappingService
from app.seed.factories import CompanyFactory, EmploymentFactory, UserFactory
from app.tests import BaseTest


class TestAnonymizationDateTruncation(BaseTest):
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
