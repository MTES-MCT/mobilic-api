from datetime import datetime, timedelta, date

from flask.ctx import AppContext
from freezegun import freeze_time
from time import sleep

from app.domain.log_activities import log_activity
from app.models import Mission
from app.models.activity import ActivityType
from app.tests import (
    BaseTest,
    UserFactory,
    CompanyFactory,
    AuthenticatedUserContext,
)
from app import app, db
from app.helpers.errors import AuthorizationError
from app.domain.permissions import (
    company_admin,
    is_employed_by_company_over_period,
    can_actor_read_mission,
    check_actor_can_write_on_mission_over_period,
)


class TestAuthorization(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.departed_admin = UserFactory.create(
            post__company=self.company,
            post__has_admin_rights=True,
            post__start_date=date(2019, 1, 1),
            post__end_date=date(2020, 1, 1),
        )
        self.team_leader = UserFactory.create(post__company=self.company)
        self.workers = [
            UserFactory.create(post__company=self.company) for u in range(0, 3)
        ]
        self.departed_worker = UserFactory.create(
            post__company=self.company,
            post__start_date=date(2019, 1, 1),
            post__end_date=date(2020, 1, 1),
        )
        self.current_user = self.team_leader
        self._app_context = AppContext(app)
        self.current_user_context = AuthenticatedUserContext(
            user=self.current_user
        )
        self._app_context.__enter__()
        self.current_user_context.__enter__()

    def tearDown(self):
        self.current_user_context.__exit__(None, None, None)
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _create_mission(self):
        return Mission.create(
            submitter=self.team_leader,
            reception_time=datetime.now(),
            company=self.company,
        )

    def test_is_company_admin(self):
        self.assertEqual(company_admin(self.admin, self.company), True)
        self.assertEqual(company_admin(self.admin, self.company.id), True)

        with freeze_time(date(2019, 6, 1)):
            self.assertEqual(company_admin(self.admin, self.company), True)
            self.assertEqual(company_admin(self.admin, self.company.id), True)

            self.assertEqual(
                company_admin(self.departed_admin, self.company), True
            )
            self.assertEqual(
                company_admin(self.departed_admin, self.company.id), True
            )

        with freeze_time(date(2020, 6, 1)):
            self.assertEqual(company_admin(self.admin, self.company), True)
            self.assertEqual(company_admin(self.admin, self.company.id), True)

            self.assertEqual(
                company_admin(self.departed_admin, self.company), False
            )
            self.assertEqual(
                company_admin(self.departed_admin, self.company.id), False
            )

    def test_is_employed_by_company_over_period(self):
        for start_date, end_date in [
            (date(2019, 1, 1), date(2019, 2, 2)),
            (date(2019, 6, 1), date(2019, 7, 2)),
            (date(2019, 1, 1), date(2020, 1, 1)),
        ]:
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.admin, self.company, start=start_date, end=end_date
                ),
                True,
            )
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.team_leader,
                    self.company,
                    start=start_date,
                    end=end_date,
                ),
                True,
            )
            for worker in self.workers:
                self.assertEqual(
                    is_employed_by_company_over_period(
                        worker, self.company, start=start_date, end=end_date
                    ),
                    True,
                )
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.departed_worker,
                    self.company,
                    start=start_date,
                    end=end_date,
                ),
                True,
            )

        for start_date, end_date in [
            (date(2018, 1, 1), date(2018, 2, 2)),
            (date(2019, 6, 1), date(2020, 1, 2)),
            (date(2018, 1, 1), date(2021, 1, 1)),
        ]:
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.admin, self.company, start=start_date, end=end_date
                ),
                True,
            )
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.team_leader,
                    self.company,
                    start=start_date,
                    end=end_date,
                ),
                True,
            )
            for worker in self.workers:
                self.assertEqual(
                    is_employed_by_company_over_period(
                        worker, self.company, start=start_date, end=end_date
                    ),
                    True,
                )
            self.assertEqual(
                is_employed_by_company_over_period(
                    self.departed_worker,
                    self.company,
                    start=start_date,
                    end=end_date,
                ),
                False,
            )

    def test_can_actor_access_mission(self):
        mission = self._create_mission()

        self.assertEqual(can_actor_read_mission(self.admin, mission), True)
        self.assertEqual(
            can_actor_read_mission(self.team_leader, mission), True
        )
        for w in self.workers:
            self.assertEqual(can_actor_read_mission(w, mission), False)

        with freeze_time(date(2019, 6, 1)):
            self.assertEqual(
                can_actor_read_mission(self.departed_admin, mission), True
            )

        with freeze_time(date(2020, 6, 1)):
            self.assertEqual(
                can_actor_read_mission(self.departed_admin, mission), False
            )

        log_activity(
            submitter=self.team_leader,
            user=self.workers[0],
            mission=mission,
            type=ActivityType.WORK,
            switch_mode=True,
            reception_time=datetime.now(),
            start_time=datetime.now(),
        )
        self.assertEqual(can_actor_read_mission(self.admin, mission), True)
        self.assertEqual(
            can_actor_read_mission(self.team_leader, mission), True
        )
        for w in self.workers:
            self.assertEqual(
                can_actor_read_mission(w, mission), w == self.workers[0]
            )

    def test_can_actor_write_on_mission(self):
        mission = self._create_mission()

        check_actor_can_write_on_mission_over_period(self.admin, mission)
        check_actor_can_write_on_mission_over_period(self.team_leader, mission)

        for w in self.workers:
            with self.assertRaises(AuthorizationError):
                check_actor_can_write_on_mission_over_period(w, mission),
