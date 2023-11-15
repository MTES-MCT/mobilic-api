from datetime import datetime

from app import app, db
from app.domain.log_activities import log_activity
from app.helpers.errors import AuthorizationError
from app.models import Mission
from app.models.activity import ActivityType, Activity
from app.seed import UserFactory, CompanyFactory
from app.tests import (
    BaseTest,
    AuthenticatedUserContext,
)
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestDeletedMissions(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)
        with app.app_context():
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
                    start_time=datetime(2022, 1, 1, 1),
                    end_time=datetime(2022, 1, 1, 2),
                )

            db.session.flush()
            db.session.commit()

    def tearDown(self):
        super().tearDown()

    def test_missions_with_dismissed_activities_are_returned(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker.id,
            query=ApiRequests.cancel_activity,
            variables=dict(
                activity_id=self.activity_by_worker.id,
            ),
        )
        self.assertTrue(
            response["data"]["activities"]["cancelActivity"]["success"]
        )

        query_company_mission_deleted_response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query="""
            query CompanyMissionsDeleted($id: Int!) {
            company(id: $id) {
            missionsDeleted {
                edges {
                node {
                    id
                    name
                    receptionTime
                    activities {
                    id
                    dismissedAt
                    }
                   }
                }
              }
            }
        }
            """,
            variables=dict(id=self.company.id),
        )

        print(query_company_mission_deleted_response)

        self.assertTrue(
            query_company_mission_deleted_response["data"]["company"][
                "missionsDeleted"
            ]
        )

        node = query_company_mission_deleted_response["data"]["company"][
            "missionsDeleted"
        ]["edges"][0]["node"]
        self.assertTrue(
            node["activities"] and node["activities"][0]["dismissedAt"]
        )

    def test_missions_without_dismissed_activities_are_not_returned(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker.id,
            query=ApiRequests.query_company_mission_deleted,
            variables=dict(
                id=self.company.id,
            ),
        )
        self.assertTrue(response["data"]["company"]["missionsDeleted"])

        node = response["data"]["company"]["missionsDeleted"]["edges"][0][
            "node"
        ]
        self.assertFalse(
            node["activities"]
            or any(activity["dismissedAt"] for activity in node["activities"])
        )
