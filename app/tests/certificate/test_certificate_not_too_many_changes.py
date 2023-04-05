from datetime import date, datetime, timedelta

from flask.ctx import AppContext

from app import app, db
from app.domain.certificate_criteria import (
    compute_not_too_many_changes,
)
from app.domain.log_activities import log_activity
from app.helpers.time import previous_month_period
from app.models import Mission
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
    UserFactory,
    AuthenticatedUserContext,
)
from app.tests import BaseTest


class TestCertificateNotTooManyChanges(BaseTest):
    def setUp(self):
        super().setUp()

        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)
        self.start, self.end = previous_month_period(date(2023, 3, 28))

        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_too_many_changes_ok_no_activities(self):
        self.assertTrue(
            compute_not_too_many_changes(self.company, self.start, self.end)
        )

    def test_too_many_changes_ok_one_activity_unmodified(self):
        mission_date = datetime(2023, 2, 15)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=mission_date,
            )
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime(2023, 2, 15, 10, 5),
                start_time=datetime(2023, 2, 15, 10),
            )
            db.session.commit()
        self.assertTrue(
            compute_not_too_many_changes(self.company, self.start, self.end)
        )

    def test_too_many_changes_ko_one_activity_modified(self):
        mission_date = datetime(2023, 2, 15)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=mission_date,
            )
            activity = log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime(2023, 2, 15, 10, 5),
                start_time=datetime(2023, 2, 15, 10),
            )
            db.session.commit()
        with AuthenticatedUserContext(user=self.admin):
            activity.revise(
                revision_time=datetime(2023, 2, 15, 18),
                start_time=datetime(2023, 2, 15, 11),
                end_time=datetime(2023, 2, 15, 13),
            )
        self.assertFalse(
            compute_not_too_many_changes(self.company, self.start, self.end)
        )

    def test_too_many_changes_several_activities(self):
        mission_date = datetime(2023, 2, 15)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=mission_date,
            )
            activities = [
                log_activity(
                    submitter=self.worker,
                    user=self.worker,
                    mission=mission,
                    type=ActivityType.WORK,
                    switch_mode=True,
                    reception_time=datetime(2023, 2, 15, start_hour, 35),
                    start_time=datetime(2023, 2, 15, start_hour),
                    end_time=datetime(2023, 2, 15, start_hour, 30),
                )
                for start_hour in range(7, 22)
            ]
            db.session.commit()

        # Activities are not modified => ok
        self.assertTrue(
            compute_not_too_many_changes(self.company, self.start, self.end)
        )
        with AuthenticatedUserContext(user=self.admin):
            activities[0].revise(
                revision_time=datetime(2023, 2, 16, 10),
                start_time=activities[0].start_time + timedelta(minutes=5),
                end_time=datetime(2023, 2, 15, 13) + timedelta(minutes=5),
            )

        # Only one modified is still ok
        self.assertTrue(
            compute_not_too_many_changes(self.company, self.start, self.end)
        )

        with AuthenticatedUserContext(user=self.admin):
            activities[1].revise(
                revision_time=datetime(2023, 2, 16, 10),
                start_time=activities[1].start_time + timedelta(minutes=5),
                end_time=datetime(2023, 2, 15, 13) + timedelta(minutes=5),
            )

        # Two modified is not ok
        self.assertFalse(
            compute_not_too_many_changes(self.company, self.start, self.end)
        )
