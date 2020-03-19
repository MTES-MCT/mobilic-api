from datetime import datetime

from app import db
from app.helpers.time import to_timestamp
from app.models import TeamEnrollment
from app.models.activity import (
    InputableActivityType,
    ActivityType,
    Activity,
    ActivityDismissType,
)
from app.models.team_enrollment import TeamEnrollmentType
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
        self._enroll(self.team_mates, datetime(2020, 2, 7, 8))
        half_day_events = {
            datetime(2020, 2, 7, 8): {
                "type": InputableActivityType.DRIVE,
                "driver_id": self.team_leader.id,
            },
            datetime(2020, 2, 7, 10): {"type": InputableActivityType.WORK},
            datetime(2020, 2, 7, 12): {"type": InputableActivityType.BREAK},
            datetime(2020, 2, 7, 14): {"type": InputableActivityType.WORK},
            datetime(2020, 2, 7, 16): {"type": InputableActivityType.BREAK},
        }
        self.submit_half_day_events = SubmitEventsTest(
            "log_activities",
            [
                {**event_props, "event_time": to_timestamp(event_time),}
                for event_time, event_props in half_day_events.items()
            ],
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 7, 16, 10),
        )
        for event_time, event_params in half_day_events.items():
            for team_member in self.team:
                activity_type = event_params["type"]
                if (
                    activity_type == ActivityType.DRIVE
                    and team_member.id != event_params["driver_id"]
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
        end_day_events = {
            datetime(2020, 2, 7, 18): {
                "type": InputableActivityType.DRIVE,
                "driver_id": self.team_leader.id,
            },
            datetime(2020, 2, 7, 19): {
                "type": InputableActivityType.DRIVE,
                "driver_id": self.team_mates[0].id,
            },
            datetime(2020, 2, 7, 20): {"type": InputableActivityType.REST},
        }
        self.submit_end_day_events = SubmitEventsTest(
            "log_activities",
            [
                {**event_props, "event_time": to_timestamp(event_time),}
                for event_time, event_props in end_day_events.items()
            ],
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 7, 20, 1),
        )
        for event_time, event_params in end_day_events.items():
            for team_member in self.team:
                activity_type = event_params["type"]
                if (
                    activity_type == ActivityType.DRIVE
                    and team_member.id != event_params["driver_id"]
                ):
                    activity_type = ActivityType.SUPPORT
                self.submit_end_day_events.should_create(
                    type=activity_type,
                    event_time=event_time,
                    user_id=team_member.id,
                    submitter_id=self.team_leader.id,
                    start_time=event_time,
                    dismissed_at=None,
                    revised_at=None,
                )
        self.submit_all_day_events = SubmitEventsTestChain(
            [self.submit_half_day_events, self.submit_end_day_events]
        )

    def _enroll(self, mates, time):
        for mate in mates:
            db.session.add(
                TeamEnrollment(
                    type=TeamEnrollmentType.ENROLL,
                    action_time=time,
                    event_time=time,
                    submitter_id=self.team_leader.id,
                    user_id=mate.id,
                    company_id=self.company.id,
                )
            )
        db.session.commit()

    def test_cancel_activity_as_team_leader(self):
        self.submit_all_day_events.test(self)

        activity_to_cancel_start_time = datetime(2020, 2, 7, 16)
        activity_to_cancel = Activity.query.filter(
            Activity.start_time == activity_to_cancel_start_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        test_case = SubmitEventsTest(
            "cancel_activities",
            dict(
                event_id=activity_to_cancel.id,
                event_time=to_timestamp(datetime(2020, 2, 7, 21)),
            ),
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 7, 21, 1),
        )
        for team_member in self.team:
            test_case.should_dismiss(
                type=ActivityType.BREAK,
                user_id=team_member.id,
                start_time=activity_to_cancel_start_time,
                dismiss_type=ActivityDismissType.USER_CANCEL,
                dismissed_at=datetime(2020, 2, 7, 21),
                revised_at=None,
            )
        test_case.test(self)

    def test_cancel_activity_as_simple_member(self):
        team_mate = self.team_mates[0]
        self.submit_all_day_events.test(self)

        activity_to_cancel_start_time = datetime(2020, 2, 7, 16)
        activity_to_cancel = Activity.query.filter(
            Activity.start_time == activity_to_cancel_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        test_case = SubmitEventsTest(
            "cancel_activities",
            dict(
                event_id=activity_to_cancel.id,
                event_time=to_timestamp(datetime(2020, 2, 7, 21)),
            ),
            submitter=team_mate,
            submit_time=datetime(2020, 2, 7, 21, 1),
        ).should_dismiss(
            type=ActivityType.BREAK,
            user_id=team_mate.id,
            start_time=activity_to_cancel_start_time,
            dismiss_type=ActivityDismissType.USER_CANCEL,
            dismissed_at=datetime(2020, 2, 7, 21),
            revised_at=None,
        )
        test_case.test(self)

    def test_cancel_activity_on_running_day(self):
        self.submit_half_day_events.test(self)

        activity_to_cancel_start_time = datetime(2020, 2, 7, 16)
        activity_to_cancel = Activity.query.filter(
            Activity.start_time == activity_to_cancel_start_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        test_case = SubmitEventsTest(
            "cancel_activities",
            dict(
                event_id=activity_to_cancel.id,
                event_time=to_timestamp(datetime(2020, 2, 7, 21)),
            ),
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 7, 21, 1),
        )
        for team_member in self.team:
            test_case.should_dismiss(
                type=ActivityType.BREAK,
                user_id=team_member.id,
                start_time=activity_to_cancel_start_time,
                dismiss_type=ActivityDismissType.USER_CANCEL,
                dismissed_at=datetime(2020, 2, 7, 21),
                revised_at=None,
            )
        test_case.test(self)

    def test_cancel_multiple_activities_in_one_batch(self):
        self.submit_all_day_events.test(self)

        first_activity_to_cancel_start_time = datetime(2020, 2, 7, 16)
        first_activity_to_cancel = Activity.query.filter(
            Activity.start_time == first_activity_to_cancel_start_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        second_activity_to_cancel_start_time = datetime(2020, 2, 7, 8)
        second_activity_to_cancel = Activity.query.filter(
            Activity.start_time == second_activity_to_cancel_start_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        test_case = SubmitEventsTest(
            "cancel_activities",
            [
                dict(
                    event_id=first_activity_to_cancel.id,
                    event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                ),
                dict(
                    event_id=second_activity_to_cancel.id,
                    event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                ),
            ],
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 7, 21, 1),
        )
        for team_member in self.team:
            test_case.should_dismiss(
                type=ActivityType.BREAK,
                user_id=team_member.id,
                start_time=first_activity_to_cancel_start_time,
                dismiss_type=ActivityDismissType.USER_CANCEL,
                dismissed_at=datetime(2020, 2, 7, 21),
                revised_at=None,
            )
            test_case.should_dismiss(
                type=ActivityType.DRIVE
                if team_member == self.team_leader
                else ActivityType.SUPPORT,
                user_id=team_member.id,
                start_time=second_activity_to_cancel_start_time,
                dismiss_type=ActivityDismissType.USER_CANCEL,
                dismissed_at=datetime(2020, 2, 7, 21),
                revised_at=None,
            )
        test_case.test(self)

    def test_cancel_multiple_activities_in_multiple_batches(self):
        team_mate = self.team_mates[0]
        self.submit_all_day_events.test(self)

        first_activity_to_cancel_start_time = datetime(2020, 2, 7, 16)
        first_activity_to_cancel = Activity.query.filter(
            Activity.start_time == first_activity_to_cancel_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        first_test_case = SubmitEventsTest(
            "cancel_activities",
            dict(
                event_id=first_activity_to_cancel.id,
                event_time=to_timestamp(datetime(2020, 2, 7, 21)),
            ),
            submitter=team_mate,
            submit_time=datetime(2020, 2, 7, 21, 1),
        ).should_dismiss(
            type=ActivityType.BREAK,
            user_id=team_mate.id,
            start_time=first_activity_to_cancel_start_time,
            dismiss_type=ActivityDismissType.USER_CANCEL,
            dismissed_at=datetime(2020, 2, 7, 21),
            revised_at=None,
        )

        second_activity_to_cancel_start_time = datetime(2020, 2, 7, 8)
        second_activity_to_cancel = Activity.query.filter(
            Activity.start_time == second_activity_to_cancel_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        second_test_case = SubmitEventsTest(
            "cancel_activities",
            dict(
                event_id=second_activity_to_cancel.id,
                event_time=to_timestamp(datetime(2020, 2, 7, 22)),
            ),
            submitter=team_mate,
            submit_time=datetime(2020, 2, 7, 22, 1),
        ).should_dismiss(
            type=ActivityType.SUPPORT,
            user_id=team_mate.id,
            start_time=second_activity_to_cancel_start_time,
            dismiss_type=ActivityDismissType.USER_CANCEL,
            dismissed_at=datetime(2020, 2, 7, 22),
        )
        SubmitEventsTestChain([first_test_case, second_test_case]).test(self)

    def test_cancel_activity_handle_neighbour_inconsistencies(self):
        """ We are cancelling a BREAK activity located between two WORK activities

        The second work activity should be marked as duplicate after the cancel
        """
        team_mate = self.team_mates[1]
        self.submit_all_day_events.test(self)

        activity_to_cancel_start_time = datetime(2020, 2, 7, 12)
        activity_to_cancel = Activity.query.filter(
            Activity.start_time == activity_to_cancel_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        test_case = (
            SubmitEventsTest(
                "cancel_activities",
                dict(
                    event_id=activity_to_cancel.id,
                    event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                ),
                submitter=team_mate,
                submit_time=datetime(2020, 2, 7, 21, 1),
            )
            .should_dismiss(
                type=ActivityType.BREAK,
                user_id=team_mate.id,
                start_time=activity_to_cancel_start_time,
                dismiss_type=ActivityDismissType.USER_CANCEL,
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

    def test_cancel_activity_handle_complex_neighbour_inconsistencies(self):
        """ We are cancelling all the activities of the day following the 4pm break

        The end of the day should be set to 4pm after the cancel
        """
        team_mate = self.team_mates[2]
        self.submit_all_day_events.test(self)

        first_activity_to_cancel_start_time = datetime(2020, 2, 7, 18)
        first_activity_to_cancel = Activity.query.filter(
            Activity.start_time == first_activity_to_cancel_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        second_activity_to_cancel_start_time = datetime(2020, 2, 7, 19)
        second_activity_to_cancel = Activity.query.filter(
            Activity.start_time == second_activity_to_cancel_start_time,
            Activity.user_id == team_mate.id,
        ).one()

        test_case = (
            SubmitEventsTest(
                "cancel_activities",
                [
                    dict(
                        event_id=first_activity_to_cancel.id,
                        event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                    ),
                    dict(
                        event_id=second_activity_to_cancel.id,
                        event_time=to_timestamp(datetime(2020, 2, 7, 21)),
                    ),
                ],
                submitter=team_mate,
                submit_time=datetime(2020, 2, 7, 21, 1),
            )
            .should_dismiss(
                type=ActivityType.SUPPORT,
                user_id=team_mate.id,
                start_time=first_activity_to_cancel_start_time,
                dismiss_type=ActivityDismissType.USER_CANCEL,
                dismissed_at=datetime(2020, 2, 7, 21),
            )
            .should_dismiss(
                type=ActivityType.SUPPORT,
                user_id=team_mate.id,
                start_time=second_activity_to_cancel_start_time,
                dismiss_type=ActivityDismissType.USER_CANCEL,
                is_driver_switch=True,
                dismissed_at=datetime(2020, 2, 7, 21),
            )
            .should_dismiss(
                type=ActivityType.REST,
                user_id=team_mate.id,
                start_time=datetime(2020, 2, 7, 20),
                dismiss_type=ActivityDismissType.NO_ACTIVITY_SWITCH,
                dismissed_at=datetime(2020, 2, 7, 21),
            )
            .should_create(
                type=ActivityType.REST,
                user_id=team_mate.id,
                start_time=datetime(2020, 2, 7, 16),
                dismissed_at=None,
                event_time=datetime(2020, 2, 7, 21),
            )
        )
        test_case.test(self)

    def test_cancel_multiple_activities_by_multiple_cancellors(self):
        """ We are cancelling some activities for the whole team, after one of the team mates did the cancellation on his part.

        The new cancel should proceed for the other team mates
        """
        self.test_cancel_activity_handle_complex_neighbour_inconsistencies()

        team = [self.team_leader] + self.team_mates[:-1]

        first_activity_to_cancel_start_time = datetime(2020, 2, 7, 18)
        first_activity_to_cancel = Activity.query.filter(
            Activity.start_time == first_activity_to_cancel_start_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        second_activity_to_cancel_start_time = datetime(2020, 2, 7, 19)
        second_activity_to_cancel = Activity.query.filter(
            Activity.start_time == second_activity_to_cancel_start_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        test_case = SubmitEventsTest(
            "cancel_activities",
            [
                dict(
                    event_id=first_activity_to_cancel.id,
                    event_time=to_timestamp(datetime(2020, 2, 7, 22)),
                ),
                dict(
                    event_id=second_activity_to_cancel.id,
                    event_time=to_timestamp(datetime(2020, 2, 7, 22)),
                ),
            ],
            submitter=self.team_leader,
            submit_time=datetime(2020, 2, 7, 22, 1),
        )
        for team_member in team:
            test_case.should_dismiss(
                type=ActivityType.DRIVE
                if team_member == self.team_leader
                else ActivityType.SUPPORT,
                user_id=team_member.id,
                start_time=first_activity_to_cancel_start_time,
                dismiss_type=ActivityDismissType.USER_CANCEL,
                dismissed_at=datetime(2020, 2, 7, 22),
            ).should_dismiss(
                type=ActivityType.DRIVE
                if team_member == self.team_mates[0]
                else ActivityType.SUPPORT,
                user_id=team_member.id,
                start_time=second_activity_to_cancel_start_time,
                dismiss_type=ActivityDismissType.USER_CANCEL,
                is_driver_switch=True
                if team_member == self.team_mates[1]
                else None,
                dismissed_at=datetime(2020, 2, 7, 22),
            ).should_dismiss(
                type=ActivityType.REST,
                user_id=team_member.id,
                start_time=datetime(2020, 2, 7, 20),
                dismiss_type=ActivityDismissType.NO_ACTIVITY_SWITCH,
                dismissed_at=datetime(2020, 2, 7, 22),
            ).should_create(
                type=ActivityType.REST,
                user_id=team_member.id,
                start_time=datetime(2020, 2, 7, 16),
                dismissed_at=None,
            )
        test_case.test(self)
