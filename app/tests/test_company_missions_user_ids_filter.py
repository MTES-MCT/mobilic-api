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


class TestCompanyMissionsUserIdsFilter(BaseTest):
    def setUp(self):
        super().setUp()
        self._app_context = AppContext(app)
        self._app_context.__enter__()

        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker_1 = UserFactory.create(post__company=self.company)
        self.worker_2 = UserFactory.create(post__company=self.company)

        self.mission_of_worker_1 = Mission.create(
            submitter=self.worker_1,
            company=self.company,
            reception_time=datetime.now(),
        )
        with AuthenticatedUserContext(self.worker_1):
            log_activity(
                submitter=self.worker_1,
                user=self.worker_1,
                mission=self.mission_of_worker_1,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=get_time(how_many_days_ago=2, hour=10),
                end_time=get_time(how_many_days_ago=2, hour=14),
            )

        self.mission_of_worker_2 = Mission.create(
            submitter=self.worker_2,
            company=self.company,
            reception_time=datetime.now(),
        )
        with AuthenticatedUserContext(self.worker_2):
            log_activity(
                submitter=self.worker_2,
                user=self.worker_2,
                mission=self.mission_of_worker_2,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=get_time(how_many_days_ago=1, hour=10),
                end_time=get_time(how_many_days_ago=1, hour=14),
            )
        db.session.commit()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _query_mission_ids(self, user_ids=None):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.query_company_missions,
            variables=dict(
                id=self.company.id,
                userIds=user_ids,
            ),
        )
        self.assertIsNone(response.get("errors"))
        edges = response["data"]["company"]["missions"]["edges"]
        return {int(edge["node"]["id"]) for edge in edges}

    def test_no_user_ids_returns_all_missions(self):
        mission_ids = self._query_mission_ids(user_ids=None)
        self.assertEqual(
            mission_ids,
            {self.mission_of_worker_1.id, self.mission_of_worker_2.id},
        )

    def test_user_ids_filters_to_participant_missions(self):
        mission_ids = self._query_mission_ids(user_ids=[self.worker_1.id])
        self.assertEqual(mission_ids, {self.mission_of_worker_1.id})

    def test_user_ids_with_multiple_users_is_a_union(self):
        mission_ids = self._query_mission_ids(
            user_ids=[self.worker_1.id, self.worker_2.id]
        )
        self.assertEqual(
            mission_ids,
            {self.mission_of_worker_1.id, self.mission_of_worker_2.id},
        )

    def test_user_ids_with_no_matching_participant_returns_nothing(self):
        other_worker = UserFactory.create(post__company=self.company)
        mission_ids = self._query_mission_ids(user_ids=[other_worker.id])
        self.assertEqual(mission_ids, set())
