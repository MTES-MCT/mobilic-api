from datetime import datetime

from app.models import Mission
from app.models.activity import (
    InputableActivityType,
    ActivityType,
    ActivityDismissType,
    Activity,
)
from app.tests import BaseTest, UserFactory
from app.tests.helpers import (
    DBEntryUpdate,
    ForeignKey,
    test_db_changes,
    make_authenticated_request,
    ApiRequests,
)


class TestLogActivities(BaseTest):
    def setUp(self):
        super().setUp()
        self.team_leader = UserFactory.create(
            first_name="Tim", last_name="Leader"
        )
        self.company = self.team_leader.company
        self.team_mates = [
            UserFactory.create(
                company=self.company, first_name="Tim", last_name="Mate"
            )
            for i in range(0, 3)
        ]
        self.team = [self.team_leader] + self.team_mates

    def begin_mission(self, time, submit_time=None, should_fail=None):
        expected_db_changes = dict(
            mission=DBEntryUpdate(
                model=Mission,
                before=None,
                after=dict(event_time=time, submitter_id=self.team_leader.id),
            ),
            **{
                "activity"
                + str(i): DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        event_time=time,
                        submitter_id=self.team_leader.id,
                        user_id=team_mate.id,
                        type=ActivityType.WORK,
                        mission_id=ForeignKey("mission"),
                    ),
                )
                for i, team_mate in enumerate(self.team)
            },
        )
        with test_db_changes(
            expected_db_changes if not should_fail else {},
            watch_models=[Activity, Mission],
        ):
            response = make_authenticated_request(
                time=submit_time or time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.begin_mission,
                variables=dict(
                    first_activity_type=ActivityType.WORK,
                    event_time=time,
                    team=[{"id": mate.id} for mate in self.team_mates],
                ),
                request_should_fail_with=should_fail,
            )

        if not should_fail:
            return response["data"]["activity"]["beginMission"]["mission"]

    def test_log_simple_activity(self, time=datetime(2020, 2, 7, 6)):
        """ Logging one simple activity for everybody
        """
        self.begin_mission(time)

    def test_cannot_log_in_advance(self):
        event_time = datetime(2020, 2, 7, 6)
        self.begin_mission(
            event_time, submit_time=datetime(2020, 2, 7, 5), should_fail=True
        )

    def test_can_only_log_inputable_activities(self):
        event_time = datetime(2020, 2, 7, 6)
        mission = self.begin_mission(event_time)
        with test_db_changes({}, watch_models=[Activity, Mission]):
            make_authenticated_request(
                time=datetime(2020, 2, 7, 8),
                submitter_id=self.team_leader.id,
                query=ApiRequests.log_activity,
                variables=dict(
                    type=ActivityType.REST,
                    event_time=datetime(2020, 2, 7, 8),
                    mission_id=mission["id"],
                    driver_id=None,
                ),
                request_should_fail_with={"status": 400},
            )

    def test_log_linear_activity_list(self, day=datetime(2020, 2, 7)):
        """ Logging a list of activities for the team,

        with long durations and valid activity switches
        """
        time = datetime(day.year, day.month, day.day, 6)
        mission = self.begin_mission(time)

        second_event_time = datetime(day.year, day.month, day.day, 7)
        second_event_type = InputableActivityType.DRIVE
        third_event_time = datetime(day.year, day.month, day.day, 9, 30)
        third_event_type = InputableActivityType.WORK
        fourth_event_time = datetime(day.year, day.month, day.day, 12, 13)
        fourth_event_type = InputableActivityType.BREAK
        fifth_event_time = datetime(day.year, day.month, day.day, 12, 53)
        fifth_event_type = InputableActivityType.WORK

        expected_changes = []
        for team_member in self.team:
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=InputableActivityType.DRIVE
                        if team_member == self.team_leader
                        else ActivityType.SUPPORT,
                        event_time=second_event_time,
                        user_time=second_event_time,
                        user_id=team_member.id,
                        submitter_id=self.team_leader.id,
                        mission_id=mission["id"],
                    ),
                )
            )
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=third_event_type,
                        event_time=third_event_time,
                        user_time=third_event_time,
                        user_id=team_member.id,
                        submitter_id=self.team_leader.id,
                        mission_id=mission["id"],
                    ),
                )
            )
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=fourth_event_type,
                        event_time=fourth_event_time,
                        user_time=fourth_event_time,
                        user_id=team_member.id,
                        submitter_id=self.team_leader.id,
                        mission_id=mission["id"],
                    ),
                )
            )
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=fifth_event_type,
                        event_time=fifth_event_time,
                        user_time=fifth_event_time,
                        user_id=team_member.id,
                        submitter_id=self.team_leader.id,
                        mission_id=mission["id"],
                    ),
                )
            )

        with test_db_changes(
            expected_changes, watch_models=[Activity, Mission]
        ):
            make_authenticated_request(
                time=second_event_time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.log_activity,
                variables=dict(
                    type=second_event_type,
                    event_time=second_event_time,
                    mission_id=mission["id"],
                    driver_id=self.team_leader.id,
                ),
            )
            make_authenticated_request(
                time=third_event_time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.log_activity,
                variables=dict(
                    type=third_event_type,
                    event_time=third_event_time,
                    mission_id=mission["id"],
                    driver_id=self.team_leader.id,
                ),
            )
            make_authenticated_request(
                time=fourth_event_time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.log_activity,
                variables=dict(
                    type=fourth_event_type,
                    event_time=fourth_event_time,
                    mission_id=mission["id"],
                    driver_id=self.team_leader.id,
                ),
            )
            make_authenticated_request(
                time=fifth_event_time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.log_activity,
                variables=dict(
                    type=fifth_event_type,
                    event_time=fifth_event_time,
                    mission_id=mission["id"],
                    driver_id=self.team_leader.id,
                ),
            )

        return mission

    def test_log_activity_list_with_activity_duplicates(self):
        """ Logging activities for the team,

        with two subsequent activities having the same type (no switch)
        """
        mission = self.test_log_linear_activity_list()

        sixth_event_time = datetime(2020, 2, 7, 14)
        sixth_event_type = InputableActivityType.WORK

        expected_changes = []
        for team_member in self.team:
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=sixth_event_type,
                        event_time=sixth_event_time,
                        user_time=sixth_event_time,
                        user_id=team_member.id,
                        submitter_id=self.team_leader.id,
                        mission_id=mission["id"],
                        dismiss_type=ActivityDismissType.NO_ACTIVITY_SWITCH,
                    ),
                )
            )

        with test_db_changes(
            expected_changes, watch_models=[Activity, Mission]
        ):
            make_authenticated_request(
                time=sixth_event_time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.log_activity,
                variables=dict(
                    type=sixth_event_type,
                    event_time=sixth_event_time,
                    mission_id=mission["id"],
                    driver_id=self.team_leader.id,
                ),
            )

    def test_log_standard_mission(self, day=datetime(2020, 2, 7)):
        mission = self.test_log_linear_activity_list(day)

        mission_end_time = datetime(day.year, day.month, day.day, 16)

        expected_changes = []
        for team_member in self.team:
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=ActivityType.REST,
                        event_time=mission_end_time,
                        user_time=mission_end_time,
                        user_id=team_member.id,
                        submitter_id=self.team_leader.id,
                        mission_id=mission["id"],
                    ),
                )
            )

        with test_db_changes(
            expected_changes, watch_models=[Activity, Mission]
        ):
            make_authenticated_request(
                time=mission_end_time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.end_mission,
                variables=dict(
                    event_time=mission_end_time, mission_id=mission["id"]
                ),
            )
        return mission

    def test_should_not_log_activity_twice(self):
        self.begin_mission(datetime(2020, 2, 7, 6))
        self.begin_mission(datetime(2020, 2, 7, 6), should_fail=True)
