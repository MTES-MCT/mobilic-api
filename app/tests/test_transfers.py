from datetime import datetime

from app.models.activity import ActivityType, Activity
from app.tests import BaseTest, CompanyFactory, UserFactory
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestTransfers(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.employee = UserFactory.create(
            post__company=self.company, post__has_admin_rights=False
        )

    def test_transfer_is_created(self):
        """A manager logs a transfer once a mission is validated by employee"""
        create_mission_response = make_authenticated_request(
            time=None,
            submitter_id=self.employee.id,
            query=ApiRequests.create_mission,
            variables={"company_id": self.company.id},
        )
        mission_id = create_mission_response["data"]["activities"][
            "createMission"
        ]["id"]

        ## employee logs time in mission
        start_time = datetime(2022, 2, 23, 14)
        end_time = datetime(2022, 2, 23, 16)
        make_authenticated_request(
            time=None,
            submitter_id=self.employee.id,
            query=ApiRequests.log_activity,
            variables=dict(
                start_time=start_time,
                end_time=end_time,
                mission_id=mission_id,
                type=ActivityType.WORK,
                user_id=self.employee.id,
                switch=False,
            ),
            request_should_fail_with=None,
        )

        ## admin logs a transfer
        start_time = datetime(2022, 2, 23, 6)
        end_time = datetime(2022, 2, 23, 14)
        res = make_authenticated_request(
            time=None,
            submitter_id=self.admin.id,
            query=ApiRequests.log_activity,
            variables=dict(
                start_time=start_time,
                end_time=end_time,
                mission_id=mission_id,
                type=ActivityType.TRANSFER,
                user_id=self.admin.id,
                switch=False,
            ),
            request_should_fail_with=None,
        )
        print(res)

        activities = Activity.query.filter_by(
            type=ActivityType.TRANSFER, mission_id=mission_id
        ).all()
        self.assertEqual(len(activities), 1)
