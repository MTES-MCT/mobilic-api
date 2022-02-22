from datetime import datetime

from app.models import Mission
from app.models.activity import (
    ActivityType,
    Activity,
)
from app.tests import BaseTest
from app.tests.helpers import (
    DBEntryUpdate,
    ForeignKey,
    test_db_changes,
    make_authenticated_request,
    ApiRequests,
)
from app.seed import UserFactory, CompanyFactory


class TestLogActivities(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.team_leader = UserFactory.create(
            first_name="Tim", last_name="Leader", post__company=self.company
        )
        self.team_mates = [
            UserFactory.create(
                post__company=self.company, first_name="Tim", last_name="Mate"
            )
            for i in range(0, 3)
        ]
        self.team = [self.team_leader] + self.team_mates
        self.team_ids = [u.id for u in self.team]

    def begin_mission(self, time, submit_time=None, should_fail=None):
        expected_db_changes = dict(
            mission=DBEntryUpdate(
                model=Mission,
                before=None,
                after=dict(
                    reception_time=submit_time or time,
                    submitter_id=self.team_leader.id,
                ),
            ),
            **{
                "activity"
                + str(i): DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        reception_time=time,
                        start_time=time,
                        submitter_id=self.team_leader.id,
                        user_id=team_mate_id,
                        type=ActivityType.WORK,
                        mission_id=ForeignKey("mission"),
                    ),
                )
                for i, team_mate_id in enumerate(self.team_ids)
            },
        )
        with test_db_changes(
            expected_db_changes
            if not should_fail
            else {"mission": expected_db_changes["mission"]},
            watch_models=[Activity, Mission],
        ):
            create_mission_response = make_authenticated_request(
                time=submit_time or time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.create_mission,
                variables={"company_id": self.company.id},
            )
            mission_id = create_mission_response["data"]["activities"][
                "createMission"
            ]["id"]
            for team_mate_id in self.team_ids:
                make_authenticated_request(
                    time=submit_time or time,
                    submitter_id=self.team_leader.id,
                    query=ApiRequests.log_activity,
                    variables=dict(
                        start_time=time,
                        mission_id=mission_id,
                        type=ActivityType.WORK,
                        user_id=team_mate_id,
                        switch=True,
                    ),
                    request_should_fail_with=should_fail,
                )

        if not should_fail:
            return mission_id

    def test_log_simple_activity(self, time=datetime(2020, 2, 7, 6)):
        """Logging one simple activity for everybody"""
        self.begin_mission(time)

    def test_cannot_log_in_advance(self):
        reception_time = datetime(2020, 2, 7, 6)
        self.begin_mission(
            reception_time,
            submit_time=datetime(2020, 2, 7, 5),
            should_fail=True,
        )

    def test_can_only_log_valid_activity_types(self):
        time = datetime(2020, 2, 7, 6)
        mission_id = self.begin_mission(time)
        with test_db_changes({}, watch_models=[Activity, Mission]):
            make_authenticated_request(
                time=datetime(2020, 2, 7, 8),
                submitter_id=self.team_leader.id,
                query=ApiRequests.log_activity,
                variables=dict(
                    type="invalid_value",
                    start_time=datetime(2020, 2, 7, 8),
                    mission_id=mission_id,
                ),
                request_should_fail_with={"status": 400},
            )

    def test_log_linear_activity_list(self, day=datetime(2020, 2, 7)):
        """Logging a list of activities for the team,

        with long durations and valid activity switches
        """
        time = datetime(day.year, day.month, day.day, 6)
        mission_id = self.begin_mission(time)

        second_event_time = datetime(day.year, day.month, day.day, 7)
        third_event_time = datetime(day.year, day.month, day.day, 9, 30)
        third_event_type = ActivityType.WORK
        break_event_time = datetime(day.year, day.month, day.day, 12, 13)
        fifth_event_time = datetime(day.year, day.month, day.day, 12, 53)
        fifth_event_type = ActivityType.WORK

        expected_changes = []
        for team_mate_id in self.team_ids:
            expected_changes.extend(
                [
                    DBEntryUpdate(
                        model=Activity,
                        before=None,
                        after=dict(
                            type=ActivityType.DRIVE
                            if team_mate_id == self.team_leader.id
                            else ActivityType.SUPPORT,
                            reception_time=second_event_time,
                            start_time=second_event_time,
                            end_time=third_event_time,
                            user_id=team_mate_id,
                            submitter_id=self.team_leader.id,
                            mission_id=mission_id,
                        ),
                    ),
                    DBEntryUpdate(
                        model=Activity,
                        before=dict(
                            user_id=team_mate_id,
                            mission_id=mission_id,
                            start_time=time,
                            end_time=None,
                        ),
                        after=dict(
                            user_id=team_mate_id,
                            mission_id=mission_id,
                            start_time=time,
                            end_time=second_event_time,
                        ),
                    ),
                ]
            )
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=third_event_type,
                        reception_time=third_event_time,
                        start_time=third_event_time,
                        end_time=break_event_time,
                        user_id=team_mate_id,
                        submitter_id=self.team_leader.id,
                        mission_id=mission_id,
                    ),
                )
            )
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=fifth_event_type,
                        reception_time=fifth_event_time,
                        start_time=fifth_event_time,
                        end_time=None,
                        user_id=team_mate_id,
                        submitter_id=self.team_leader.id,
                        mission_id=mission_id,
                    ),
                )
            )

        with test_db_changes(
            expected_changes, watch_models=[Activity, Mission]
        ):
            for team_mate_id in self.team_ids:
                make_authenticated_request(
                    time=second_event_time,
                    submitter_id=self.team_leader.id,
                    query=ApiRequests.log_activity,
                    variables=dict(
                        type=ActivityType.DRIVE
                        if team_mate_id == self.team_leader.id
                        else ActivityType.SUPPORT,
                        start_time=second_event_time,
                        mission_id=mission_id,
                        user_id=team_mate_id,
                    ),
                )
                response = make_authenticated_request(
                    time=third_event_time,
                    submitter_id=self.team_leader.id,
                    query=ApiRequests.log_activity,
                    variables=dict(
                        type=third_event_type,
                        start_time=third_event_time,
                        mission_id=mission_id,
                        user_id=team_mate_id,
                    ),
                )
                activity_to_stop_id = response["data"]["activities"][
                    "logActivity"
                ]["id"]
                make_authenticated_request(
                    time=break_event_time,
                    submitter_id=self.team_leader.id,
                    query=ApiRequests.edit_activity,
                    variables=dict(
                        activity_id=activity_to_stop_id,
                        end_time=break_event_time,
                    ),
                )
                make_authenticated_request(
                    time=fifth_event_time,
                    submitter_id=self.team_leader.id,
                    query=ApiRequests.log_activity,
                    variables=dict(
                        type=fifth_event_type,
                        start_time=fifth_event_time,
                        mission_id=mission_id,
                        user_id=team_mate_id,
                    ),
                )

        return mission_id

    def test_log_activity_list_with_activity_duplicates(self):
        """Logging activities for the team,

        with two subsequent activities having the same type (no switch)
        """
        mission_id = self.test_log_linear_activity_list()

        sixth_event_time = datetime(2020, 2, 7, 14)

        sixth_event_type = ActivityType.WORK

        with test_db_changes([], watch_models=[Activity, Mission]):
            for team_mate_id in self.team_ids:
                make_authenticated_request(
                    time=sixth_event_time,
                    submitter_id=self.team_leader.id,
                    query=ApiRequests.log_activity,
                    variables=dict(
                        type=sixth_event_type,
                        start_time=sixth_event_time,
                        mission_id=mission_id,
                        user_id=team_mate_id,
                    ),
                )

    def test_log_standard_mission(self, day=datetime(2020, 2, 7)):
        mission_id = self.test_log_linear_activity_list(day)

        fifth_event_time = datetime(day.year, day.month, day.day, 12, 53)
        mission_end_time = datetime(day.year, day.month, day.day, 16)

        expected_changes = []
        for team_mate_id in self.team_ids:
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=dict(
                        user_id=team_mate_id,
                        mission_id=mission_id,
                        start_time=fifth_event_time,
                        end_time=None,
                    ),
                    after=dict(
                        user_id=team_mate_id,
                        mission_id=mission_id,
                        start_time=fifth_event_time,
                        end_time=mission_end_time,
                    ),
                )
            )

        with test_db_changes(
            expected_changes, watch_models=[Activity, Mission]
        ):
            for team_mate_id in self.team_ids:
                make_authenticated_request(
                    time=mission_end_time,
                    submitter_id=self.team_leader.id,
                    query=ApiRequests.end_mission,
                    variables=dict(
                        end_time=mission_end_time,
                        mission_id=mission_id,
                        user_id=team_mate_id,
                    ),
                )
        return mission_id

    def test_should_not_log_activity_twice(self):
        self.begin_mission(datetime(2020, 2, 7, 6))
        self.begin_mission(datetime(2020, 2, 7, 6), should_fail=True)
