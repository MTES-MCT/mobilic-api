from datetime import datetime

from app.models.activity import (
    ActivityType,
    Activity,
)
from app.seed import UserFactory, CompanyFactory
from app.tests import BaseTest
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
)


class TestCancelMission(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.team_leader = UserFactory.create(
            first_name="Tim", last_name="Leader", post__company=self.company
        )
        self.team_mate = UserFactory.create(
            first_name="Tim", last_name="Mate", post__company=self.company
        )

    def begin_mission_single_user(self, time):
        create_mission_response = make_authenticated_request(
            time=time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.create_mission,
            variables={"company_id": self.company.id},
        )
        mission_id = create_mission_response["data"]["activities"][
            "createMission"
        ]["id"]
        make_authenticated_request(
            time=time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.log_activity,
            variables=dict(
                start_time=time,
                mission_id=mission_id,
                type=ActivityType.WORK,
                user_id=self.team_leader.id,
                switch=True,
            ),
        )
        return mission_id

    def begin_team_mission(self, time):
        create_mission_response = make_authenticated_request(
            time=time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.create_mission,
            variables={"company_id": self.company.id},
        )
        mission_id = create_mission_response["data"]["activities"][
            "createMission"
        ]["id"]
        make_authenticated_request(
            time=time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.log_activity,
            variables=dict(
                start_time=time,
                mission_id=mission_id,
                type=ActivityType.WORK,
                user_id=self.team_leader.id,
                switch=True,
            ),
        )
        make_authenticated_request(
            time=time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.log_activity,
            variables=dict(
                start_time=time,
                mission_id=mission_id,
                type=ActivityType.WORK,
                user_id=self.team_mate.id,
                switch=True,
            ),
        )
        return mission_id

    def test_cancel_mission_one_user(self, day=datetime(2020, 2, 7)):
        time = datetime(day.year, day.month, day.day, 6)
        mission_id = self.begin_mission_single_user(time)

        second_event_time = datetime(day.year, day.month, day.day, 7)

        make_authenticated_request(
            time=second_event_time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.log_activity,
            variables=dict(
                type=ActivityType.DRIVE,
                start_time=second_event_time,
                mission_id=mission_id,
                user_id=self.team_leader.id,
                switch=True,
            ),
        )

        make_authenticated_request(
            time=second_event_time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.cancel_mission,
            variables=dict(
                mission_id=mission_id,
                user_id=self.team_leader.id,
            ),
        )
        result_activities = Activity.query.filter(
            Activity.mission_id == mission_id,
            Activity.user_id == self.team_leader.id,
        ).all()
        self.assertEqual(len(result_activities), 2)
        for activity in result_activities:
            self.assertEqual(self.team_leader.id, activity.dismiss_author_id)
            self.assertIsNotNone(activity.dismissed_at)

    def test_cancel_mission_with_teammate(self, day=datetime(2020, 2, 7)):
        time = datetime(day.year, day.month, day.day, 6)
        mission_id = self.begin_team_mission(time)

        make_authenticated_request(
            time=time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.cancel_mission,
            variables=dict(
                mission_id=mission_id,
                user_id=self.team_mate.id,
            ),
        )
        result_activities = Activity.query.filter(
            Activity.mission_id == mission_id
        ).all()
        cancelled_activities = list(
            filter(
                lambda act: act.user_id == self.team_mate.id, result_activities
            )
        )
        not_cancelled_activities = list(
            filter(
                lambda act: act.user_id != self.team_mate.id, result_activities
            )
        )
        self.assertEqual(len(cancelled_activities), 1)
        self.assertEqual(len(not_cancelled_activities), 1)
        for activity in cancelled_activities:
            self.assertEqual(self.team_leader.id, activity.dismiss_author_id)
            self.assertIsNotNone(activity.dismissed_at)

        for activity in not_cancelled_activities:
            self.assertIsNone(activity.dismiss_author_id)
            self.assertIsNone(activity.dismissed_at)
