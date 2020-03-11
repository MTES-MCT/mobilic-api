from datetime import datetime

from app.helpers.time import to_timestamp
from app.models.activity import (
    InputableActivityType,
    ActivityType,
    ActivityDismissType,
)
from app.tests import BaseTest, UserFactory

from app.tests.helpers import SubmitEventsTest, SubmitEventsTestChain


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

    def test_log_simple_activity(self):
        """ Logging one simple activity for everybody
        """
        event_time = datetime(2020, 2, 7, 4, 19, 6, 977000)
        test_case = SubmitEventsTest(
            "log_activities",
            dict(
                type=InputableActivityType.WORK,
                event_time=to_timestamp(event_time),
                team=[{"id": u.id} for u in self.team],
            ),
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 7, 23),
        )
        for team_member in self.team:
            test_case.should_create(
                type=ActivityType.WORK,
                event_time=event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=event_time,
                dismissed_at=None,
                revised_at=None,
            )
        test_case.test(self)

    def test_cannot_log_in_advance(self):
        event_time = datetime(2020, 2, 7, 4, 19, 6, 977000)
        test_case = SubmitEventsTest(
            "log_activities",
            dict(
                type=InputableActivityType.WORK,
                event_time=to_timestamp(event_time),
                team=[{"id": u.id} for u in self.team],
            ),
            submit_time=datetime(2020, 2, 7, 3),
            submitter=self.team_leader,
        )
        test_case.test(self)

    def test_can_only_log_inputable_activities(self):
        event_time = datetime(2020, 2, 7, 4, 19, 6, 977000)
        test_case = SubmitEventsTest(
            "log_activities",
            dict(
                type=ActivityType.SUPPORT,
                event_time=to_timestamp(event_time),
                team=[{"id": u.id} for u in self.team],
            ),
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 7, 23),
            request_should_fail_with={"status": 400},
        )
        test_case.test(self)

    def test_log_linear_activity_list(self):
        """ Logging a list of activities for the team,

        with long durations and valid activity switches
        """
        first_event_time = datetime(2020, 2, 7, 4, 19, 6, 977000)
        second_event_time = datetime(2020, 2, 7, 7, 5, 6, 977000)
        third_event_time = datetime(2020, 2, 7, 9, 49, 6, 977000)
        fourth_event_time = datetime(2020, 2, 7, 12, 43, 6, 977000)
        test_case = (
            SubmitEventsTest(
                "log_activities",
                dict(
                    type=InputableActivityType.DRIVE,
                    event_time=to_timestamp(first_event_time),
                    team=[{"id": u.id} for u in self.team],
                    driver_idx=0,  # team_leader,
                ),
                submit_time=datetime(2020, 2, 9, 23),
                submitter=self.team_leader,
            )
            .add_event(
                dict(
                    type=InputableActivityType.BREAK,
                    event_time=to_timestamp(
                        second_event_time
                    ),  # 2020-02-07 07:05
                    team=[{"id": u.id} for u in self.team],
                )
            )
            .add_event(
                dict(
                    type=InputableActivityType.WORK,
                    event_time=to_timestamp(
                        third_event_time
                    ),  # 2020-02-07 07:05
                    team=[{"id": u.id} for u in self.team],
                )
            )
            .add_event(
                dict(
                    type=InputableActivityType.BREAK,
                    event_time=to_timestamp(
                        fourth_event_time
                    ),  # 2020-02-07 07:05
                    team=[{"id": u.id} for u in self.team],
                )
            )
        )
        for team_member in self.team:
            test_case.should_create(
                type=ActivityType.DRIVE
                if team_member == self.team_leader
                else ActivityType.SUPPORT,
                event_time=first_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=first_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.BREAK,
                event_time=second_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=second_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.WORK,
                event_time=third_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=third_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.BREAK,
                event_time=fourth_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=fourth_event_time,
                dismissed_at=None,
                revised_at=None,
            )
        test_case.test(self)

    def test_log_activity_list_with_short_durations(self):
        """ Logging activities for the team,

        with several ones having a very short duration (few secs). These should not be logged
        """
        first_event_time = datetime(2020, 2, 7, 4, 19, 6, 977000)
        second_event_time = datetime(2020, 2, 7, 7, 5, 6, 977000)
        second_event_time_plus_dt = datetime(2020, 2, 7, 7, 5, 7, 977000)
        second_event_time_plus_2_dt = datetime(2020, 2, 7, 7, 5, 8, 977000)
        third_event_time = datetime(2020, 2, 7, 12, 43, 6, 977000)
        test_case = SubmitEventsTest(
            "log_activities",
            [
                dict(
                    type=InputableActivityType.DRIVE,
                    event_time=to_timestamp(
                        first_event_time
                    ),  # 2020-02-07 04:19
                    team=[{"id": u.id} for u in self.team],
                    driver_idx=0,  # team_leader,
                ),
                dict(
                    type=InputableActivityType.BREAK,
                    event_time=to_timestamp(
                        second_event_time
                    ),  # 2020-02-07 07:05
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.REST,
                    event_time=to_timestamp(
                        second_event_time_plus_dt
                    ),  # 2020-02-07 07:05
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.WORK,
                    event_time=to_timestamp(
                        second_event_time_plus_2_dt
                    ),  # 2020-02-07 07:05
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.REST,
                    event_time=to_timestamp(
                        third_event_time
                    ),  # 2020-02-07 12:43
                    team=[{"id": u.id} for u in self.team],
                ),
            ],
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 9, 23),
        )
        for team_member in self.team:
            test_case.should_create(
                type=ActivityType.DRIVE
                if team_member == self.team_leader
                else ActivityType.SUPPORT,
                event_time=first_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=first_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.WORK,
                event_time=second_event_time_plus_2_dt,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=second_event_time_plus_2_dt,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.REST,
                event_time=third_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=third_event_time,
                dismissed_at=None,
                revised_at=None,
            )
        test_case.test(self)

    def test_log_activity_list_with_activity_duplicates(self):
        """ Logging activities for the team,

        with two subsequent activities having the same type (no switch)
        """
        first_event_time = datetime(2020, 2, 7, 4, 19, 6, 977000)
        second_event_time = datetime(2020, 2, 7, 7, 5, 6, 977000)
        third_event_time = datetime(2020, 2, 7, 12, 43, 6, 977000)
        fourth_event_time = datetime(2020, 2, 7, 12, 43, 6, 977000)
        test_case = SubmitEventsTest(
            "log_activities",
            [
                dict(
                    type=InputableActivityType.DRIVE,
                    event_time=to_timestamp(
                        first_event_time
                    ),  # 2020-02-07 04:19
                    team=[{"id": u.id} for u in self.team],
                    driver_idx=0,  # team_leader,
                ),
                dict(
                    type=InputableActivityType.WORK,
                    event_time=to_timestamp(
                        second_event_time
                    ),  # 2020-02-07 07:05
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.WORK,
                    event_time=to_timestamp(
                        third_event_time
                    ),  # 2020-02-07 09:49
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.REST,
                    event_time=to_timestamp(
                        fourth_event_time
                    ),  # 2020-02-07 12:43
                    team=[{"id": u.id} for u in self.team],
                ),
            ],
            submit_time=datetime(2020, 2, 9, 23),
            submitter=self.team_leader,
        )
        for team_member in self.team:
            test_case.should_create(
                type=ActivityType.DRIVE
                if team_member == self.team_leader
                else ActivityType.SUPPORT,
                event_time=first_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=first_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.WORK,
                event_time=second_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=second_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.WORK,
                event_time=third_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=third_event_time,
                dismiss_type=ActivityDismissType.NO_ACTIVITY_SWITCH,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.REST,
                event_time=fourth_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=fourth_event_time,
                dismissed_at=None,
                revised_at=None,
            )
        test_case.test(self)

    def test_several_logs_of_activity_lists(self):
        """ Logging several lists of activities for the team,

        with a few edge cases
        """

        # Log 1 : standard day for the whole team
        first_event_time = datetime(2020, 2, 7, 4, 19, 6, 977000)
        second_event_time = datetime(2020, 2, 7, 7, 5, 6, 977000)
        third_event_time = datetime(2020, 2, 7, 9, 49, 6, 977000)
        fourth_event_time = datetime(2020, 2, 7, 12, 43, 6, 977000)
        fifth_event_time = datetime(2020, 2, 7, 14, 00, 6, 977000)
        test_case = SubmitEventsTest(
            "log_activities",
            [
                dict(
                    type=InputableActivityType.DRIVE,
                    event_time=to_timestamp(first_event_time),
                    team=[{"id": u.id} for u in self.team],
                    driver_idx=0,  # team_leader,
                ),
                dict(
                    type=InputableActivityType.BREAK,
                    event_time=to_timestamp(second_event_time),
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.WORK,
                    event_time=to_timestamp(third_event_time),
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.BREAK,
                    event_time=to_timestamp(fourth_event_time),
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.WORK,
                    event_time=to_timestamp(fifth_event_time),
                    team=[{"id": u.id} for u in self.team],
                ),
            ],
            submit_time=datetime(2020, 2, 7, 15),
            submitter=self.team_leader,
        )
        for team_member in self.team:
            test_case.should_create(
                type=ActivityType.DRIVE
                if team_member == self.team_leader
                else ActivityType.SUPPORT,
                event_time=first_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=first_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.BREAK,
                event_time=second_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=second_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.WORK,
                event_time=third_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=third_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.BREAK,
                event_time=fourth_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=fourth_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            test_case.should_create(
                type=ActivityType.WORK,
                event_time=fifth_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=fifth_event_time,
                dismissed_at=None,
                revised_at=None,
            )

        # Log 2 : The team leader is rewriting the past logged period
        # for himself only
        first_event_time = datetime(2020, 2, 7, 8, 30, 6, 977000)
        second_event_time = datetime(2020, 2, 7, 16, 27, 6, 977000)
        third_event_time = datetime(2020, 2, 8, 8, 5, 6, 977000)
        second_test_case = SubmitEventsTest(
            "log_activities",
            [
                dict(
                    type=InputableActivityType.DRIVE,
                    event_time=to_timestamp(first_event_time),
                    team=[{"id": self.team_leader.id}],
                    driver_idx=0,  # team_leader,
                ),
                dict(
                    type=InputableActivityType.REST,
                    event_time=to_timestamp(second_event_time),
                    team=[{"id": self.team_leader.id}],
                ),
                dict(
                    type=InputableActivityType.DRIVE,
                    event_time=to_timestamp(third_event_time),
                    team=[{"id": self.team_leader.id}],
                    driver_idx=0,
                ),
            ],
            submit_time=datetime(2020, 2, 8, 12),
            submitter=self.team_leader,
        )
        second_test_case.should_create(
            type=ActivityType.DRIVE,
            event_time=first_event_time,
            user_id=self.team_leader.id,
            submitter_id=self.team_leader.id,
            start_time=first_event_time,
            dismissed_at=None,
            revised_at=None,
        )
        second_test_case.should_create(
            type=ActivityType.REST,
            event_time=second_event_time,
            user_id=self.team_leader.id,
            submitter_id=self.team_leader.id,
            start_time=second_event_time,
            dismissed_at=None,
            revised_at=None,
        )
        second_test_case.should_create(
            type=ActivityType.DRIVE,
            event_time=third_event_time,
            user_id=self.team_leader.id,
            submitter_id=self.team_leader.id,
            start_time=third_event_time,
            dismissed_at=None,
            revised_at=None,
        )

        # Log 3 : The team leader is logging again for the whole team,
        # for a new day whose start is very close to the last team leader's log
        team_leader_last_activity_event_time = third_event_time
        first_event_time = datetime(2020, 2, 8, 8, 5, 7, 977000)
        second_event_time = datetime(2020, 2, 8, 10, 49, 6, 977000)
        third_event_time = datetime(2020, 2, 8, 13, 33, 6, 977000)
        fourth_event_time = datetime(2020, 2, 8, 16, 17, 6, 977000)
        third_test_case = SubmitEventsTest(
            "log_activities",
            [
                dict(
                    type=InputableActivityType.DRIVE,
                    event_time=to_timestamp(first_event_time),
                    team=[{"id": u.id} for u in self.team],
                    driver_idx=1,  # team_leader,
                ),
                dict(
                    type=InputableActivityType.BREAK,
                    event_time=to_timestamp(second_event_time),
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.WORK,
                    event_time=to_timestamp(third_event_time),
                    team=[{"id": u.id} for u in self.team],
                ),
                dict(
                    type=InputableActivityType.REST,
                    event_time=to_timestamp(fourth_event_time),
                    team=[{"id": u.id} for u in self.team],
                ),
            ],
            submit_time=datetime(2020, 2, 8, 23),
            submitter=self.team_leader,
        )
        third_test_case.should_delete(
            type=ActivityType.DRIVE,
            event_time=team_leader_last_activity_event_time,
            user_id=self.team_leader.id,
            submitter_id=self.team_leader.id,
            start_time=team_leader_last_activity_event_time,
        )
        for team_member in self.team:
            third_test_case.should_create(
                type=ActivityType.DRIVE
                if team_member == self.team_mates[0]
                else ActivityType.SUPPORT,
                event_time=first_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=first_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            third_test_case.should_create(
                type=ActivityType.BREAK,
                event_time=second_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=second_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            third_test_case.should_create(
                type=ActivityType.WORK,
                event_time=third_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=third_event_time,
                dismissed_at=None,
                revised_at=None,
            )
            third_test_case.should_create(
                type=ActivityType.REST,
                event_time=fourth_event_time,
                user_id=team_member.id,
                submitter_id=self.team_leader.id,
                start_time=fourth_event_time,
                dismissed_at=None,
                revised_at=None,
            )

        test_suite = (
            SubmitEventsTestChain()
            + test_case
            + second_test_case
            + third_test_case
        )
        test_suite.test(self)
