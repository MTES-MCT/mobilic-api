from datetime import date, datetime

from flask.ctx import AppContext

from app import app, db
from app.domain.certificate_criteria import (
    certificate_expiration,
    compute_be_active,
    compute_company_certification,
    previous_month_period,
)
from app.domain.log_activities import log_activity
from app.models import Mission
from app.models.activity import ActivityType
from app.seed import CompanyFactory, UserFactory
from app.seed.factories import CompanyFactory, UserFactory
from app.tests import AuthenticatedUserContext, BaseTest


class TestCertificateCriteria(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)

        self._app_context = AppContext(app)
        self._app_context.__enter__()

        with AuthenticatedUserContext(user=self.worker):
            self.mission_by_worker = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=datetime.now(),
            )
            self.activity_by_worker = log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=self.mission_by_worker,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=datetime(2023, 1, 1, 1),
                end_time=datetime(2023, 1, 1, 2),
            )
        db.session.commit()

        with AuthenticatedUserContext(user=self.admin):
            self.mission_by_admin = Mission.create(
                submitter=self.admin,
                company=self.company,
                reception_time=datetime.now(),
            )
            self.activity_by_admin = log_activity(
                submitter=self.admin,
                user=self.worker,
                mission=self.mission_by_admin,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=datetime(2023, 2, 1, 1),
                end_time=datetime(2023, 2, 3, 2),
            )

            log_activity(
                submitter=self.admin,
                user=self.worker,
                mission=self.mission_by_worker,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=datetime(2022, 1, 2, 1),
                end_time=datetime(2022, 1, 2, 2),
            )
        db.session.flush()
        db.session.commit()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_previous_month_period(self):
        start, end = previous_month_period(date(2023, 3, 28))
        self.assertEqual(start, date(2023, 2, 1))
        self.assertEqual(end, date(2023, 2, 28))

    def test_certificate_expiration(self):
        expiration_date = certificate_expiration(
            date(2023, 3, 28), lifetime_month=6
        )
        self.assertEqual(expiration_date, date(2023, 8, 31))

    def test_compute_be_active(self):
        be_active = compute_be_active(
            self.company, date(2023, 2, 1), date(2023, 2, 28)
        )
        self.assertFalse(be_active)

    def test_compute_company_certification(self):
        compute_company_certification(self.company)
        # should not fail
