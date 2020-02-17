from freezegun import freeze_time

from app.helpers.time import from_timestamp
from app.models.activity import (
    InputableActivityTypes,
    ActivityValidationStatus,
    ActivityTypes,
)
from app.tests import BaseTest, UserFactory
from app import app, db
from app.models import User
from sqlalchemy.orm import joinedload


class TestLogActivities(BaseTest):
    def setUp(self):
        super().setUp()
        self.team_leader = UserFactory.create()
        self.company = self.team_leader.company
        self.team_mates = [
            UserFactory.create(company=self.company) for i in range(0, 3)
        ]
        self.team = [self.team_leader] + self.team_mates

    def _create_activities_and_check_logs(
        self, submitter, activities, should_fail_parsing=False
    ):
        all_user_ids = [
            uid for activity in activities for uid in activity["user_ids"]
        ]
        users = (
            User.query.options(joinedload(User.activities))
            .filter(User.id.in_(all_user_ids))
            .all()
        )
        db.session.commit()

        existing_activity_ids_per_user = {
            user: dict(
                all=[a.id for a in user.activities],
                current=user.current_acknowledged_activity.id
                if user.current_acknowledged_activity
                else None,
            )
            for user in users
        }

        with app.test_client(mock_authentication_with_user=submitter) as c:
            response = c.post_graphql(
                """
                mutation ($data: [SingleActivityInput]!) {
                    logActivities (data: $data) {
                        activities {
                            id
                            type
                            validationStatus
                            eventTime
                        }
                    }
                }
                """,
                variables=dict(
                    data=[
                        dict(
                            team=[{"id": value} for value in a["user_ids"]],
                            eventTime=a["event_time"],
                            type=a["type"],
                            driverIdx=a.get("driver_idx", 0),
                        )
                        for a in activities
                    ]
                ),
            )
        if should_fail_parsing:
            self.assertEqual(response.status_code, 400)
        else:
            self.assertEqual(response.status_code, 200)

        for user in users:
            # Get the newly created activities
            real_activity_count_diff = len(user.activities) - len(
                existing_activity_ids_per_user[user]["all"]
            )
            real_new_activities = [
                a
                for a in user.activities
                if a.id not in existing_activity_ids_per_user[user]["all"]
            ]

            # Get the activities that should have been created
            expected_new_activities = []
            expected_activity_count_diff = 0
            for activity in activities:
                if user.id in activity["user_ids"]:
                    user_specifics = activity.get("user_specifics", {}).get(
                        user.id, {}
                    )
                    if activity.get("should_not_create") or user_specifics.get(
                        "should_not_create"
                    ):
                        pass
                    else:
                        expected_new_activities.append(activity)
                        if not activity.get(
                            "should_replace"
                        ) and not user_specifics.get("should_replace"):
                            expected_activity_count_diff += 1

            # Sort actual and expected activities by event time
            real_new_activities.sort(key=lambda a: a.event_time)
            expected_new_activities.sort(key=lambda a: a["event_time"])

            # Checks
            ## 1. Check that the right number of logs were created
            self.assertEqual(
                real_activity_count_diff, expected_activity_count_diff
            )
            self.assertEqual(
                len(real_new_activities), len(expected_new_activities)
            )

            ## 2. Check that the new activities were created with the expected params
            for (real_acti, exp_acti) in zip(
                real_new_activities, expected_new_activities
            ):
                user_specifics = exp_acti.get("user_specifics", {}).get(
                    user.id, {}
                )

                self.assertEqual(
                    real_acti.type,
                    user_specifics.get("type", exp_acti["type"]),
                )
                self.assertEqual(
                    real_acti.event_time,
                    from_timestamp(exp_acti["event_time"]),
                )
                self.assertEqual(real_acti.submitter, submitter)
                self.assertEqual(real_acti.company_id, submitter.company_id)
                self.assertEqual(
                    real_acti.validation_status,
                    user_specifics.get(
                        "validation_status", ActivityValidationStatus.PENDING
                    ),
                )

                # 3. In case of replace, check that the latest of the old activities was deleted
                if (
                    exp_acti.get("should_replace")
                    or user_specifics.get("should_replace") == 0
                ):
                    self.assertNotIn(
                        existing_activity_ids_per_user[user]["current"],
                        [a.id for a in user.activities],
                    )

        # Check that we didn't create new users for initially unknown user ids
        for user_id in all_user_ids:
            if user_id not in [u.id for u in users]:
                self.assertIsNone(User.query.get(user_id))

    def test_log_simple_activity(self):
        """ Logging one simple activity for everybody
        """
        with freeze_time("2020-02-07 23:00:00"):
            self._create_activities_and_check_logs(
                submitter=self.team_leader,
                activities=[
                    dict(
                        type=InputableActivityTypes.WORK,
                        event_time=1581045546977,  # 2020-02-07 04:19
                        user_ids=[u.id for u in self.team],
                    )
                ],
            )

    def test_cannot_log_in_advance(self):
        with freeze_time("2020-02-07 03:00:00"):
            self._create_activities_and_check_logs(
                submitter=self.team_leader,
                activities=[
                    dict(
                        type=InputableActivityTypes.WORK,
                        event_time=1581045546977,  # 2020-02-07 04:19
                        user_ids=[u.id for u in self.team],
                        should_not_create=True,
                    )
                ],
            )

    def test_can_only_log_inputable_activities(self):
        with freeze_time("2020-02-07 23:00:00"):
            self._create_activities_and_check_logs(
                submitter=self.team_leader,
                activities=[
                    dict(
                        type=ActivityTypes.SUPPORT,  # Can't input that
                        event_time=1581045546977,  # 2020-02-07 04:19
                        user_ids=[u.id for u in self.team],
                        should_not_create=True,
                    )
                ],
                should_fail_parsing=True,
            )

    def test_log_linear_activity_list(self):
        """ Logging a list of activities for the team,

        with long durations and valid activity switches
        """
        with freeze_time("2020-02-09 23:00:00"):
            self._create_activities_and_check_logs(
                submitter=self.team_leader,
                activities=[
                    dict(
                        type=InputableActivityTypes.DRIVE,
                        event_time=1581045546977,  # 2020-02-07 04:19
                        user_ids=[u.id for u in self.team],
                        driver_idx=0,  # team_leader,
                        user_specifics={
                            u.id: {
                                "type": ActivityTypes.SUPPORT
                            }  # For the non drivers
                            for u in self.team_mates
                        },
                    ),
                    dict(
                        type=InputableActivityTypes.BREAK,
                        event_time=1581055546977,  # 2020-02-07 07:05
                        user_ids=[u.id for u in self.team],
                    ),
                    dict(
                        type=InputableActivityTypes.WORK,
                        event_time=1581065546977,  # 2020-02-07 09:49
                        user_ids=[u.id for u in self.team],
                    ),
                    dict(
                        type=InputableActivityTypes.REST,
                        event_time=1581075546977,  # 2020-02-07 12:43
                        user_ids=[u.id for u in self.team],
                    ),
                ],
            )

    def test_log_activity_list_with_short_durations(self):
        """ Logging activities for the team,

        with several ones having a very short duration (few secs). These should not be logged
        """
        with freeze_time("2020-02-09 23:00:00"):
            self._create_activities_and_check_logs(
                submitter=self.team_leader,
                activities=[
                    dict(
                        type=InputableActivityTypes.DRIVE,
                        event_time=1581045546977,  # 2020-02-07 04:19
                        user_ids=[u.id for u in self.team],
                        driver_idx=0,  # team_leader,
                        user_specifics={
                            u.id: {
                                "type": ActivityTypes.SUPPORT
                            }  # For the non drivers
                            for u in self.team_mates
                        },
                    ),
                    dict(
                        type=InputableActivityTypes.BREAK,
                        event_time=1581055546977,  # 2020-02-07 07:05
                        user_ids=[u.id for u in self.team],
                        should_not_create=True,
                    ),
                    dict(
                        type=InputableActivityTypes.REST,
                        event_time=1581055556977,  # Only 10s after previous event time
                        user_ids=[u.id for u in self.team],
                        should_not_create=True,
                    ),
                    dict(
                        type=InputableActivityTypes.WORK,
                        event_time=1581055566977,  # Only 10s after previous event time
                        user_ids=[u.id for u in self.team],
                    ),
                    dict(
                        type=InputableActivityTypes.REST,
                        event_time=1581075546977,  # 2020-02-07 12:43
                        user_ids=[u.id for u in self.team],
                    ),
                ],
            )

    def test_log_activity_list_with_activity_duplicates(self):
        """ Logging activities for the team,

        with two subsequent activities having the same type (no switch)
        """
        with freeze_time("2020-02-09 23:00:00"):
            self._create_activities_and_check_logs(
                submitter=self.team_leader,
                activities=[
                    dict(
                        type=InputableActivityTypes.DRIVE,
                        event_time=1581045546977,  # 2020-02-07 04:19
                        user_ids=[u.id for u in self.team],
                        driver_idx=0,  # team_leader,
                        user_specifics={
                            u.id: {
                                "type": ActivityTypes.SUPPORT
                            }  # For the non drivers
                            for u in self.team_mates
                        },
                    ),
                    dict(
                        type=InputableActivityTypes.WORK,
                        event_time=1581055546977,  # 2020-02-07 07:05
                        user_ids=[u.id for u in self.team],
                    ),
                    dict(
                        type=InputableActivityTypes.WORK,
                        event_time=1581065546977,  # 2020-02-07 09:49
                        user_ids=[u.id for u in self.team],
                        user_specifics={
                            u.id: {
                                "validation_status": ActivityValidationStatus.NO_ACTIVITY_SWITCH
                            }
                            for u in self.team
                        },
                    ),
                    dict(
                        type=InputableActivityTypes.REST,
                        event_time=1581075546977,  # 2020-02-07 12:43
                        user_ids=[u.id for u in self.team],
                    ),
                ],
            )

    def test_several_logs_of_activity_lists(self):
        """ Logging several lists of activities for the team,

        with a few edge cases
        """

        # Log 1 : standard day for the whole team
        with freeze_time("2020-02-07 15:00:00"):
            self._create_activities_and_check_logs(
                submitter=self.team_leader,
                activities=[
                    dict(
                        type=InputableActivityTypes.DRIVE,
                        event_time=1581045546977,  # 2020-02-07 04:19
                        user_ids=[u.id for u in self.team],
                        driver_idx=0,  # team_leader,
                        user_specifics={
                            u.id: {
                                "type": ActivityTypes.SUPPORT
                            }  # For the non drivers
                            for u in self.team_mates
                        },
                    ),
                    dict(
                        type=InputableActivityTypes.BREAK,
                        event_time=1581055546977,  # 2020-02-07 07:05
                        user_ids=[u.id for u in self.team],
                    ),
                    dict(
                        type=InputableActivityTypes.WORK,
                        event_time=1581065546977,  # 2020-02-07 09:49
                        user_ids=[u.id for u in self.team],
                    ),
                    dict(
                        type=InputableActivityTypes.REST,
                        event_time=1581075546977,  # 2020-02-07 12:43
                        user_ids=[u.id for u in self.team],
                    ),
                ],
            )

        # Log 2 : The team leader is rewriting the past logged period
        # for himself only
        with freeze_time("2020-02-08 12:00:00"):
            self._create_activities_and_check_logs(
                submitter=self.team_leader,
                activities=[
                    dict(
                        type=InputableActivityTypes.WORK,
                        event_time=1581060556977,  # 2020-02-07 08:30
                        user_ids=[self.team_leader.id],
                        user_specifics={
                            self.team_leader.id: {
                                "validation_status": ActivityValidationStatus.CONFLICTING_WITH_HISTORY
                            }
                        },
                    ),
                    dict(
                        type=InputableActivityTypes.REST,
                        event_time=1581085546977,  # 2020-02-07 16:27
                        user_ids=[self.team_leader.id],
                        user_specifics={
                            self.team_leader.id: {
                                "validation_status": ActivityValidationStatus.NO_ACTIVITY_SWITCH
                            }
                        },
                    ),
                    dict(
                        type=InputableActivityTypes.DRIVE,
                        event_time=1581145546977,  # 2020-02-08 08:05
                        user_ids=[self.team_leader.id],
                        driver_idx=0,  # team_leader,
                    ),
                ],
            )

            # Log 2 : The team leader is logging again for the whole team,
            # for a new day whose start is very close to the last team leader's log
            with freeze_time("2020-02-08 23:00:00"):
                self._create_activities_and_check_logs(
                    submitter=self.team_leader,
                    activities=[
                        dict(
                            type=InputableActivityTypes.DRIVE,
                            event_time=1581145566977,  # 2020-02-08 08:05
                            user_ids=[u.id for u in self.team],
                            driver_idx=1,  # First team mate
                            user_specifics={
                                self.team_leader.id: {
                                    "should_replace": True,
                                    "type": ActivityTypes.SUPPORT,
                                },
                                self.team_mates[1].id: {
                                    "type": ActivityTypes.SUPPORT
                                },
                                self.team_mates[2].id: {
                                    "type": ActivityTypes.SUPPORT
                                },
                            },
                        ),
                        dict(
                            type=InputableActivityTypes.BREAK,
                            event_time=1581155556977,  # 2020-02-07 10:49
                            user_ids=[u.id for u in self.team],
                        ),
                        dict(
                            type=InputableActivityTypes.WORK,
                            event_time=1581165546977,  # 2020-02-07 13:33
                            user_ids=[u.id for u in self.team],
                        ),
                        dict(
                            type=InputableActivityTypes.REST,
                            event_time=1581175546977,  # 2020-02-07 16:17
                            user_ids=[u.id for u in self.team],
                        ),
                    ],
                )
