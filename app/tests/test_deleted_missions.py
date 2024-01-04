from datetime import datetime

from flask.ctx import AppContext

from app import app, db
from app.domain.log_activities import log_activity
from app.models import Mission
from app.models.activity import ActivityType
from app.seed import UserFactory, CompanyFactory
from app.seed.helpers import get_time
from app.tests import (
    BaseTest,
    AuthenticatedUserContext,
)
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestDeletedMissions(BaseTest):
    def setUp(self):
        super().setUp()
        self._app_context = AppContext(app)
        self._app_context.__enter__()

        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)

        self.mission_by_worker = Mission.create(
            submitter=self.worker,
            company=self.company,
            reception_time=datetime.now(),
        )
        with AuthenticatedUserContext(self.worker):
            self.activity_1_by_worker = log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=self.mission_by_worker,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=get_time(how_many_days_ago=2, hour=10),
                end_time=get_time(how_many_days_ago=2, hour=14),
            )

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _query_deleted_missions(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.query_company_deleted_missions,
            variables=dict(
                id=self.company.id,
            ),
        )
        edges = response["data"]["company"]["missionsDeleted"]["edges"]
        return [edge["node"] for edge in edges]

    def test_missions_with_dismissed_activities_are_returned(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker.id,
            query=ApiRequests.cancel_activity,
            variables=dict(
                activity_id=self.activity_1_by_worker.id,
            ),
        )
        self.assertTrue(
            response["data"]["activities"]["cancelActivity"]["success"]
        )

        missions = self._query_deleted_missions()
        self.assertTrue(len(missions) > 0)

        first_mission = missions[0]
        self.assertTrue(first_mission["activities"])
        self.assertTrue(first_mission["activities"][0]["dismissedAt"])

    def test_missions_without_dismissed_activities_are_not_returned(self):
        missions = self._query_deleted_missions()
        self.assertTrue(len(missions) == 0)

    def test_missions_without_all_activities_dismissed_are_not_returned(self):
        with AuthenticatedUserContext(user=self.worker):
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=self.mission_by_worker,
                type=ActivityType.DRIVE,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=get_time(how_many_days_ago=2, hour=16),
                end_time=get_time(how_many_days_ago=2, hour=18),
            )
            db.session.commit()

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker.id,
            query=ApiRequests.cancel_activity,
            variables=dict(
                activity_id=self.activity_1_by_worker.id,
            ),
        )
        self.assertTrue(
            response["data"]["activities"]["cancelActivity"]["success"]
        )

        missions = self._query_deleted_missions()
        self.assertTrue(len(missions) == 0)
