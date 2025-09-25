from datetime import date, datetime

from flask.ctx import AppContext

from app import app, db
from app.controllers.activity import edit_activity
from app.domain.certificate_criteria import (
    compute_log_in_real_time,
)
from app.domain.log_activities import log_activity
from app.helpers.time import previous_month_period
from app.models import Mission
from app.models.activity import ActivityType, Activity
from app.models.queries import query_activities
from app.seed import (
    CompanyFactory,
    UserFactory,
    AuthenticatedUserContext,
)
from app.tests import BaseTest


class TestCertificateRealTime(BaseTest):
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

    def _compute_log_in_real_time(self):
        query = (
            query_activities(
                include_dismissed_activities=False,
                start_time=self.start,
                end_time=self.end,
                company_ids=[self.company.id],
            )
            .filter(Activity.type != ActivityType.OFF)
            .with_entities(Activity.id)
        )
        activity_ids = [a[0] for a in query.all()]
        return compute_log_in_real_time(activity_ids)

    def test_company_real_time_ok_no_activities(self):
        self.assertEqual(self._compute_log_in_real_time(), 1.0)

    def test_company_real_time_one_activity(self):
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
                creation_time=datetime(2023, 2, 15, 10, 5),
                start_time=datetime(2023, 2, 15, 10),
            )
            db.session.commit()
        self.assertEqual(self._compute_log_in_real_time(), 1.0)

    def test_company_not_real_time_one_activity_edge_case(self):
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
                reception_time=datetime(2023, 2, 15, 11),
                start_time=datetime(2023, 2, 15, 10),
            )
            db.session.commit()
        self.assertEqual(self._compute_log_in_real_time(), 0.0)

    def test_company_real_time_multiple_activities(self):
        mission_date = datetime(2023, 2, 2)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=mission_date,
            )
            # logged in real time
            for start_hour in range(1, 22):
                log_activity(
                    submitter=self.worker,
                    user=self.worker,
                    mission=mission,
                    type=(
                        ActivityType.WORK
                        if start_hour % 2 == 0
                        else ActivityType.DRIVE
                    ),
                    switch_mode=True,
                    reception_time=datetime(2023, 2, 2, start_hour, 5),
                    creation_time=datetime(2023, 2, 2, start_hour, 5),
                    start_time=datetime(2023, 2, 2, start_hour),
                )
            db.session.commit()

            # not logged in real time
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.SUPPORT,
                switch_mode=True,
                reception_time=datetime(2023, 2, 3, 18),
                creation_time=datetime(2023, 2, 3, 18),
                start_time=datetime(2023, 2, 3, 10),
            )
            db.session.commit()
        self.assertAlmostEqual(self._compute_log_in_real_time(), 21 / 22.0, 5)

    def test_company_not_real_time_multiple_activities(self):
        mission_date = datetime(2023, 2, 2)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=mission_date,
            )
            # logged in real time
            for start_hour in range(1, 22):
                log_activity(
                    submitter=self.worker,
                    user=self.worker,
                    mission=mission,
                    type=(
                        ActivityType.WORK
                        if start_hour % 2 == 0
                        else ActivityType.DRIVE
                    ),
                    switch_mode=True,
                    reception_time=datetime(2023, 2, 2, start_hour, 5),
                    start_time=datetime(2023, 2, 2, start_hour),
                )
            db.session.commit()

            # not logged in real time
            for start_hour in range(1, 14):
                log_activity(
                    submitter=self.worker,
                    user=self.worker,
                    mission=mission,
                    type=(
                        ActivityType.WORK
                        if start_hour % 2 == 0
                        else ActivityType.DRIVE
                    ),
                    switch_mode=True,
                    reception_time=datetime(2023, 2, 3, 18),
                    start_time=datetime(2023, 2, 3, start_hour),
                )
            db.session.commit()
        self.assertAlmostEqual(
            self._compute_log_in_real_time(), 21 / (21.0 + 12.0), 5
        )

    def test_activity_dismissed_should_not_count_as_not_real_time(self):
        mission_date = datetime(2023, 2, 2)
        with AuthenticatedUserContext(user=self.worker):
            mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=mission_date,
            )
            # real time
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime(2023, 2, 2, 10, 5),
                creation_time=datetime(2023, 2, 2, 10, 5),
                start_time=datetime(2023, 2, 2, 10),
            )
            # not real time
            not_real_time_activity = log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=True,
                reception_time=datetime(2023, 2, 3, 18),
                creation_time=datetime(2023, 2, 3, 18),
                start_time=datetime(2023, 2, 3, 10),
            )
            db.session.commit()
        # 50% are real time
        self.assertAlmostEqual(self._compute_log_in_real_time(), 0.5, 5)

        with AuthenticatedUserContext(user=self.worker):
            edit_activity(
                not_real_time_activity.id,
                cancel=True,
            )
            db.session.commit()

        # 100% are real time
        self.assertAlmostEqual(self._compute_log_in_real_time(), 1.0, 5)
