from datetime import datetime
from flask import g
from flask.ctx import AppContext

from app import app
from app.domain.company import check_company_has_no_activities
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
)
from app.seed.factories import ActivityFactory, MissionFactory, UserFactory
from app.tests import BaseTest


class TestCompaniesHasNoActivity(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.user = UserFactory.create(post__company=self.company)
        self._app_context = AppContext(app)
        self._app_context.__enter__()
        g.user = self.user

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_company_without_mission_returns_true(self):
        self.assertTrue(check_company_has_no_activities(self.company.id))

    def test_company_with_mission_without_activity_returns_true(self):
        MissionFactory.create(
            company_id=self.company.id,
            submitter_id=self.user.id,
            reception_time=datetime.now(),
        )
        self.assertTrue(check_company_has_no_activities(self.company.id))

    def test_company_with_mission_with_dismissed_activity_returns_true(self):
        reception_time = datetime.now()
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=self.user.id,
            reception_time=reception_time,
        )
        ActivityFactory.create(
            mission=mission,
            user=self.user,
            submitter=self.user,
            type=ActivityType.DRIVE,
            reception_time=reception_time,
            start_time=reception_time,
            last_update_time=reception_time,
            dismissed_at=reception_time,
            dismiss_author=self.user,
        )
        self.assertTrue(check_company_has_no_activities(self.company.id))

    def test_company_with_mission_with_activity_returns_false(self):
        reception_time = datetime.now()
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=self.user.id,
            reception_time=reception_time,
        )
        ActivityFactory.create(
            mission=mission,
            user=self.user,
            submitter=self.user,
            type=ActivityType.DRIVE,
            reception_time=reception_time,
            start_time=reception_time,
            last_update_time=reception_time,
        )
        self.assertFalse(check_company_has_no_activities(self.company.id))
