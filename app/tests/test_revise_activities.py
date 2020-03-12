from datetime import datetime

from app.helpers.time import to_timestamp
from app.models.activity import (
    InputableActivityType,
    ActivityType,
    Activity,
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
        full_day_events = {
            datetime(2020, 2, 7, 8): {
                "type": InputableActivityType.DRIVE,
                "driver_idx": 0,
            },
            datetime(2020, 2, 7, 10): {"type": InputableActivityType.WORK},
            datetime(2020, 2, 7, 12): {"type": InputableActivityType.BREAK},
            datetime(2020, 2, 7, 14): {"type": InputableActivityType.WORK},
            datetime(2020, 2, 7, 16): {"type": InputableActivityType.BREAK},
            datetime(2020, 2, 7, 18): {
                "type": InputableActivityType.DRIVE,
                "driver_idx": 0,
            },
            datetime(2020, 2, 7, 19): {
                "type": InputableActivityType.DRIVE,
                "driver_idx": 1,
            },
            datetime(2020, 2, 7, 20): {"type": InputableActivityType.REST},
        }
        self.submit_full_day_events = SubmitEventsTest(
            "log_activities",
            [
                {
                    **event_props,
                    "event_time": to_timestamp(event_time),
                    "team": [{"id": u.id} for u in self.team],
                }
                for event_time, event_props in full_day_events.items()
            ],
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 8, 20, 10),
        )
        for event_time, event_params in full_day_events.items():
            for team_member in self.team:
                activity_type = event_params["type"]
                if (
                    activity_type == ActivityType.DRIVE
                    and team_member != self.team[event_params["driver_idx"]]
                ):
                    activity_type = ActivityType.SUPPORT
                self.submit_full_day_events.should_create(
                    type=activity_type,
                    event_time=event_time,
                    user_id=team_member.id,
                    submitter_id=self.team_leader.id,
                    start_time=event_time,
                    dismissed_at=None,
                    revised_at=None,
                )
        half_day_events = {
            datetime(2020, 2, 8, 8): {
                "type": InputableActivityType.DRIVE,
                "driver_idx": 0,
            },
            datetime(2020, 2, 8, 10): {"type": InputableActivityType.WORK},
            datetime(2020, 2, 8, 12): {"type": InputableActivityType.BREAK},
            datetime(2020, 2, 8, 14): {"type": InputableActivityType.WORK},
            datetime(2020, 2, 8, 16): {"type": InputableActivityType.BREAK},
        }
        self.submit_half_day_events = SubmitEventsTest(
            "log_activities",
            [
                {
                    **event_props,
                    "event_time": to_timestamp(event_time),
                    "team": [{"id": u.id} for u in self.team],
                }
                for event_time, event_props in half_day_events.items()
            ],
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 8, 16, 1),
        )
        for event_time, event_params in half_day_events.items():
            for team_member in self.team:
                activity_type = event_params["type"]
                if (
                    activity_type == ActivityType.DRIVE
                    and team_member != self.team[event_params["driver_idx"]]
                ):
                    activity_type = ActivityType.SUPPORT
                self.submit_half_day_events.should_create(
                    type=activity_type,
                    event_time=event_time,
                    user_id=team_member.id,
                    submitter_id=self.team_leader.id,
                    start_time=event_time,
                    dismissed_at=None,
                    revised_at=None,
                )
        self.submit_full_day_events.test(self)
        self.submit_half_day_events.test(self)

    def test_revise_activity_as_team_leader(self):
        activity_to_revise_start_time = datetime(2020, 2, 7, 16)
        new_start_time = datetime(2020, 2, 7, 15)
        activity_to_revise = Activity.query.filter(
            Activity.start_time == activity_to_revise_start_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        test_case = SubmitEventsTest(
            "revise_activities",
            dict(
                event_id=activity_to_revise.id,
                start_time=to_timestamp(new_start_time),
                event_time=to_timestamp(datetime(2020, 2, 7, 21)),
            ),
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 7, 21, 1),
        )
        for team_member in self.team:
            test_case.should_create(
                type=ActivityType.BREAK,
                user_id=team_member.id,
                start_time=new_start_time,
                dismissed_at=None,
                event_time=datetime(2020, 2, 7, 21),
            )
        test_case.test(self)

    def test_revise_activity_as_simple_member(self):
        team_mate = self.team_mates[0]
        activity_to_revise_start_time = datetime(2020, 2, 7, 16)
        new_start_time = datetime(2020, 2, 7, 15)
        activity_to_revise = Activity.query.filter(
            Activity.start_time == activity_to_revise_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        test_case = SubmitEventsTest(
            "revise_activities",
            dict(
                event_id=activity_to_revise.id,
                start_time=to_timestamp(new_start_time),
                event_time=to_timestamp(datetime(2020, 2, 7, 21)),
            ),
            submitter=team_mate,
            submit_time=datetime(2020, 2, 7, 21, 1),
        ).should_create(
            type=ActivityType.BREAK,
            user_id=team_mate.id,
            start_time=new_start_time,
            dismissed_at=None,
            event_time=datetime(2020, 2, 7, 21),
            revisee_id=activity_to_revise.id,
        )
        test_case.test(self)

    def test_revise_multiple_activities_in_single_batch(self):
        team_mate = self.team_mates[0]

        first_activity_to_revise_start_time = datetime(2020, 2, 7, 16)
        first_activity_new_start_time = datetime(2020, 2, 7, 15)
        first_activity_to_revise = Activity.query.filter(
            Activity.start_time == first_activity_to_revise_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        second_activity_to_revise_start_time = datetime(2020, 2, 7, 14)
        second_activity_new_start_time = datetime(2020, 2, 7, 13)
        second_activity_to_revise = Activity.query.filter(
            Activity.start_time == second_activity_to_revise_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        test_case = (
            SubmitEventsTest(
                "revise_activities",
                [
                    dict(
                        event_id=first_activity_to_revise.id,
                        start_time=to_timestamp(first_activity_new_start_time),
                        event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                    ),
                    dict(
                        event_id=second_activity_to_revise.id,
                        start_time=to_timestamp(
                            second_activity_new_start_time
                        ),
                        event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                    ),
                ],
                submitter=team_mate,
                submit_time=datetime(2020, 2, 7, 21, 1),
            )
            .should_create(
                type=ActivityType.BREAK,
                user_id=team_mate.id,
                start_time=first_activity_new_start_time,
                dismissed_at=None,
                event_time=datetime(2020, 2, 7, 21),
                revisee_id=first_activity_to_revise.id,
            )
            .should_create(
                type=ActivityType.WORK,
                user_id=team_mate.id,
                start_time=second_activity_new_start_time,
                dismissed_at=None,
                event_time=datetime(2020, 2, 7, 21),
                revisee_id=second_activity_to_revise.id,
            )
        )
        test_case.test(self)

    def test_revise_multiple_activities_in_multiple_batches(self):
        team_mate = self.team_mates[0]

        first_activity_to_revise_start_time = datetime(2020, 2, 7, 16)
        first_activity_new_start_time = datetime(2020, 2, 7, 15)
        first_activity_to_revise = Activity.query.filter(
            Activity.start_time == first_activity_to_revise_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        second_activity_to_revise_start_time = datetime(2020, 2, 7, 14)
        second_activity_new_start_time = datetime(2020, 2, 7, 13)
        second_activity_to_revise = Activity.query.filter(
            Activity.start_time == second_activity_to_revise_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        first_test_case = SubmitEventsTest(
            "revise_activities",
            [
                dict(
                    event_id=first_activity_to_revise.id,
                    start_time=to_timestamp(first_activity_new_start_time),
                    event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                ),
            ],
            submitter=team_mate,
            submit_time=datetime(2020, 2, 7, 21, 1),
        )

        second_test_case = SubmitEventsTest(
            "revise_activities",
            [
                dict(
                    event_id=second_activity_to_revise.id,
                    start_time=to_timestamp(second_activity_new_start_time),
                    event_time=to_timestamp(datetime(2020, 2, 7, 22)),
                ),
            ],
            submitter=team_mate,
            submit_time=datetime(2020, 2, 7, 22, 1),
        )
        first_test_case.should_create(
            type=ActivityType.BREAK,
            user_id=team_mate.id,
            start_time=first_activity_new_start_time,
            dismissed_at=None,
            event_time=datetime(2020, 2, 7, 21),
            revisee_id=first_activity_to_revise.id,
        )
        second_test_case.should_create(
            type=ActivityType.WORK,
            user_id=team_mate.id,
            start_time=second_activity_new_start_time,
            dismissed_at=None,
            event_time=datetime(2020, 2, 7, 22),
            revisee_id=second_activity_to_revise.id,
        )
        SubmitEventsTestChain([first_test_case, second_test_case]).test(self)

    def test_revise_activity_with_neigbour_inconsistencies(self):
        team_mate = self.team_mates[0]
        activity_to_revise_start_time = datetime(2020, 2, 7, 12)
        new_start_time = datetime(2020, 2, 7, 17)
        activity_to_revise = Activity.query.filter(
            Activity.start_time == activity_to_revise_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        test_case = (
            SubmitEventsTest(
                "revise_activities",
                dict(
                    event_id=activity_to_revise.id,
                    start_time=to_timestamp(new_start_time),
                    event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                ),
                submitter=team_mate,
                submit_time=datetime(2020, 2, 7, 21, 1),
            )
            .should_create(
                type=ActivityType.BREAK,
                user_id=team_mate.id,
                start_time=new_start_time,
                dismiss_type=ActivityDismissType.NO_ACTIVITY_SWITCH,
                event_time=datetime(2020, 2, 7, 21),
                revisee=activity_to_revise.id,
                dismissed_at=datetime(2020, 2, 7, 21),
            )
            .should_dismiss(
                type=ActivityType.WORK,
                user_id=team_mate.id,
                start_time=datetime(2020, 2, 7, 14),
                dismiss_type=ActivityDismissType.NO_ACTIVITY_SWITCH,
                dismissed_at=datetime(2020, 2, 7, 21),
            )
        )
        test_case.test(self)

        team_mate = self.team_mates[1]
        activity_to_revise_start_time = datetime(2020, 2, 7, 12)
        new_start_time = datetime(2020, 2, 7, 15)
        activity_to_revise = Activity.query.filter(
            Activity.start_time == activity_to_revise_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        test_case = (
            SubmitEventsTest(
                "revise_activities",
                dict(
                    event_id=activity_to_revise.id,
                    start_time=to_timestamp(new_start_time),
                    event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                ),
                submitter=team_mate,
                submit_time=datetime(2020, 2, 7, 21, 1),
            )
            .should_create(
                type=ActivityType.BREAK,
                user_id=team_mate.id,
                start_time=new_start_time,
                event_time=datetime(2020, 2, 7, 21),
                revisee_id=activity_to_revise.id,
            )
            .should_dismiss(
                type=ActivityType.WORK,
                user_id=team_mate.id,
                start_time=datetime(2020, 2, 7, 14),
                dismiss_type=ActivityDismissType.NO_ACTIVITY_SWITCH,
                dismissed_at=datetime(2020, 2, 7, 21),
            )
            .should_dismiss(
                type=ActivityType.BREAK,
                user_id=team_mate.id,
                start_time=datetime(2020, 2, 7, 16),
                dismiss_type=ActivityDismissType.NO_ACTIVITY_SWITCH,
                dismissed_at=datetime(2020, 2, 7, 21),
            )
        )
        test_case.test(self)

    def test_resume_day(self):
        team_mate = self.team_mates[0]

        test_case = (
            SubmitEventsTest(
                "log_activities",
                dict(
                    event_time=to_timestamp(datetime(2020, 2, 7, 20, 30)),
                    type=ActivityType.WORK,
                    team=[{"id": team_mate.id}],
                ),
                submitter=team_mate,
                submit_time=datetime(2020, 2, 7, 21, 2),
            )
            .should_create(
                type=ActivityType.BREAK,
                user_id=team_mate.id,
                start_time=datetime(2020, 2, 7, 20),
                dismissed_at=None,
                event_time=datetime(2020, 2, 7, 20, 30),
            )
            .should_create(
                type=ActivityType.WORK,
                user_id=team_mate.id,
                start_time=datetime(2020, 2, 7, 20, 30),
                dismissed_at=None,
                revised_at=None,
            )
        )
        test_case.test(self)

    def test_revise_day_with_new_activity(self):
        team_mate = self.team_mates[0]

        test_case = SubmitEventsTest(
            "log_activities",
            dict(
                event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                start_time=to_timestamp(datetime(2020, 2, 7, 7, 30)),
                type=ActivityType.WORK,
                team=[{"id": team_mate.id}],
            ),
            submitter=team_mate,
            submit_time=datetime(2020, 2, 7, 21, 2),
        ).should_create(
            type=ActivityType.WORK,
            user_id=team_mate.id,
            start_time=datetime(2020, 2, 7, 7, 30),
            event_time=datetime(2020, 2, 7, 21),
            dismissed_at=None,
            revised_at=None,
        )
        test_case.test(self)

        test_case = SubmitEventsTest(
            "log_activities",
            dict(
                event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                start_time=to_timestamp(datetime(2020, 2, 7, 9, 50)),
                type=ActivityType.BREAK,
                team=[{"id": team_mate.id}],
            ),
            submitter=team_mate,
            submit_time=datetime(2020, 2, 7, 21, 2),
        ).should_create(
            type=ActivityType.BREAK,
            user_id=team_mate.id,
            start_time=datetime(2020, 2, 7, 9, 50),
            event_time=datetime(2020, 2, 7, 21),
            dismissed_at=None,
            revised_at=None,
        )
        test_case.test(self)

    def test_revise_lone_activity(self):
        user = UserFactory.create()

        lone_activity_submit = SubmitEventsTest(
            "log_activities",
            dict(
                event_time=to_timestamp(datetime(2020, 2, 7, 20, 30)),
                type=ActivityType.WORK,
                team=[{"id": user.id}],
            ),
            submitter=user,
            submit_time=datetime(2020, 2, 7, 21, 2),
        ).should_create(
            event_time=datetime(2020, 2, 7, 20, 30),
            user_id=user.id,
            type=ActivityType.WORK,
        )
        lone_activity_submit.test(self)

        lone_activity = Activity.query.filter(
            Activity.user_id == user.id
        ).one()

        # Revise lone activity
        SubmitEventsTest(
            "revise_activities",
            dict(
                event_id=lone_activity.id,
                start_time=to_timestamp(datetime(2020, 2, 7, 14, 30)),
                event_time=to_timestamp(datetime(2020, 2, 7, 22, 0)),
            ),
            submitter=user,
            submit_time=datetime(2020, 2, 7, 22, 1),
        ).should_create(
            event_time=datetime(2020, 2, 7, 22, 0),
            start_time=datetime(2020, 2, 7, 14, 30),
            user_id=user.id,
            type=ActivityType.WORK,
            revisee_id=lone_activity.id,
        ).test(
            self
        )

        new_lone_activity = [
            a
            for a in Activity.query.filter(Activity.user_id == user.id).all()
            if a.is_acknowledged
        ]

        self.assertEqual(len(new_lone_activity), 1)
        new_lone_activity = new_lone_activity[0]

        # Cancel lone activity
        SubmitEventsTest(
            "cancel_activities",
            dict(
                event_id=new_lone_activity.id,
                event_time=to_timestamp(datetime(2020, 2, 7, 23, 0)),
            ),
            submitter=user,
            submit_time=datetime(2020, 2, 7, 23, 1),
        ).should_dismiss(
            start_time=datetime(2020, 2, 7, 14, 30),
            user_id=user.id,
            type=ActivityType.WORK,
            revisee_id=lone_activity.id,
            dismiss_type=ActivityDismissType.USER_CANCEL,
            dismissed_at=datetime(2020, 2, 7, 23, 0),
        ).test(
            self
        )
