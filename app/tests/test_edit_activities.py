from datetime import datetime

from app.models import Mission
from app.models.activity import (
    ActivityType,
    Activity,
    ActivityDismissType,
)
from app.tests.helpers import (
    DBEntryUpdate,
    make_authenticated_request,
    test_db_changes,
    ApiRequests,
)

from app.tests.test_log_activities import TestLogActivities


class TestEditActivities(TestLogActivities):
    def _cancel_or_edit_activity_as_team_leader(
        self,
        activity_time,
        edit_time,
        new_activity_time=None,
        exclude_team_mates=None,
        additional_db_changes=None,
    ):
        exclude_team_mates = exclude_team_mates or []

        actual_activity_to_edit = Activity.query.filter(
            Activity.user_time == activity_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        expected_changes = additional_db_changes or []
        for team_member in self.team:
            activity_to_edit = Activity.query.filter(
                Activity.user_time == activity_time,
                Activity.user_id == team_member.id,
            ).one()
            if team_member not in exclude_team_mates:
                activity_data = dict(
                    type=activity_to_edit.type,
                    submitter_id=self.team_leader.id,
                    user_id=team_member.id,
                    user_time=activity_time,
                    event_time=activity_time,
                    mission_id=activity_to_edit.mission_id,
                    dismiss_type=None,
                )
                if new_activity_time:
                    activity_data["user_time"] = new_activity_time
                    activity_data["event_time"] = edit_time
                    activity_data["revisee_id"] = activity_to_edit.id
                    expected_changes.append(
                        DBEntryUpdate(
                            model=Activity, before=None, after=activity_data
                        )
                    )
                else:
                    expected_changes.append(
                        DBEntryUpdate(
                            model=Activity,
                            before=activity_data,
                            after={
                                **activity_data,
                                "dismiss_type": ActivityDismissType.USER_CANCEL,
                                "dismissed_at": edit_time,
                                "dismiss_author_id": self.team_leader.id,
                            },
                        )
                    )

        with test_db_changes(
            expected_changes, watch_models=[Activity, Mission]
        ):
            make_authenticated_request(
                time=edit_time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.edit_activity,
                variables=dict(
                    activity_id=actual_activity_to_edit.id,
                    event_time=edit_time,
                    dismiss=False if new_activity_time else True,
                    user_time=new_activity_time,
                ),
            )

    def _cancel_or_edit_activity_as_simple_member(
        self,
        team_member,
        activity_time,
        edit_time,
        new_activity_time=None,
        additional_db_changes=None,
    ):
        activity_to_edit = Activity.query.filter(
            Activity.user_time == activity_time,
            Activity.user_id == team_member.id,
        ).one()

        activity_data = dict(
            type=activity_to_edit.type,
            submitter_id=self.team_leader.id,
            user_id=team_member.id,
            user_time=activity_time,
            event_time=activity_time,
            mission_id=activity_to_edit.mission_id,
            dismiss_type=None,
        )

        expected_changes = additional_db_changes or []
        if new_activity_time:
            activity_data["user_time"] = new_activity_time
            activity_data["event_time"] = edit_time
            activity_data["revisee_id"] = activity_to_edit.id
            activity_data["submitter_id"] = team_member.id
            expected_changes.append(
                DBEntryUpdate(model=Activity, before=None, after=activity_data)
            )
        else:
            expected_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=activity_data,
                    after={
                        **activity_data,
                        "dismiss_type": ActivityDismissType.USER_CANCEL,
                        "dismissed_at": edit_time,
                        "dismiss_author_id": team_member.id,
                    },
                )
            )

        with test_db_changes(
            expected_changes, watch_models=[Activity, Mission]
        ):
            make_authenticated_request(
                time=edit_time,
                submitter_id=team_member.id,
                query=ApiRequests.edit_activity,
                variables=dict(
                    activity_id=activity_to_edit.id,
                    event_time=edit_time,
                    dismiss=False if new_activity_time else True,
                    user_time=new_activity_time,
                ),
            )

    def test_cancel_activity_as_team_leader(self):
        self.test_log_standard_mission()

        activity_to_cancel_time = datetime(
            2020, 2, 7, 9, 30
        )  # The third activity of the mission : work
        self._cancel_or_edit_activity_as_team_leader(
            activity_to_cancel_time, datetime(2020, 2, 7, 17)
        )

    def test_edit_activity_as_team_leader(self):
        self.test_log_standard_mission()

        activity_to_edit_time = datetime(
            2020, 2, 7, 9, 30
        )  # The third activity of the mission : work
        new_activity_time = datetime(2020, 2, 7, 8)
        self._cancel_or_edit_activity_as_team_leader(
            activity_to_edit_time,
            datetime(2020, 2, 7, 17),
            new_activity_time=new_activity_time,
        )

    def test_cancel_activity_as_simple_member(self):
        team_mate = self.team_mates[0]
        self.test_log_standard_mission()

        activity_to_cancel_user_time = datetime(
            2020, 2, 7, 9, 30
        )  # The third activity of the mission : work
        self._cancel_or_edit_activity_as_simple_member(
            team_mate, activity_to_cancel_user_time, datetime(2020, 2, 7, 17)
        )

    def test_edit_activity_as_simple_member(self):
        team_mate = self.team_mates[0]
        self.test_log_standard_mission()

        activity_to_edit_time = datetime(
            2020, 2, 7, 9, 30
        )  # The third activity of the mission : work
        new_activity_time = datetime(2020, 2, 7, 8)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate,
            activity_to_edit_time,
            datetime(2020, 2, 7, 17),
            new_activity_time=new_activity_time,
        )

    def test_cancel_activity_on_running_day(self):
        self.test_log_linear_activity_list()

        activity_to_cancel_time = datetime(
            2020, 2, 7, 9, 30
        )  # The third activity of the mission : work
        self._cancel_or_edit_activity_as_team_leader(
            activity_to_cancel_time, datetime(2020, 2, 7, 14)
        )

    def test_cancel_multiple_activities(self):
        self.test_log_standard_mission()
        team_mate = self.team_mates[0]

        first_activity_to_cancel_user_time = datetime(2020, 2, 7, 9, 30)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate,
            first_activity_to_cancel_user_time,
            datetime(2020, 2, 7, 17),
        )

        second_activity_to_cancel_user_time = datetime(2020, 2, 7, 6)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate,
            second_activity_to_cancel_user_time,
            datetime(2020, 2, 7, 17, 30),
        )

    def test_edit_multiple_activities(self):
        self.test_log_standard_mission()
        team_mate = self.team_mates[0]

        first_activity_to_edit_user_time = datetime(2020, 2, 7, 9, 30)
        first_activity_new_time = datetime(2020, 2, 7, 9)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate,
            first_activity_to_edit_user_time,
            datetime(2020, 2, 7, 17),
            new_activity_time=first_activity_new_time,
        )

        second_activity_to_edit_user_time = datetime(2020, 2, 7, 6)
        second_activity_new_time = datetime(2020, 2, 7, 6, 30)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate,
            second_activity_to_edit_user_time,
            datetime(2020, 2, 7, 17, 30),
            new_activity_time=second_activity_new_time,
        )

    def test_cancel_activity_handle_neighbour_inconsistencies(self):
        """ We are cancelling a BREAK activity located between two WORK activities

        The second work activity should be marked as duplicate after the cancel
        """
        self.test_log_standard_mission()

        activity_to_cancel_user_time = datetime(2020, 2, 7, 12, 13)
        activity_to_mark_as_duplicate_time = datetime(2020, 2, 7, 12, 53)

        cancel_time = datetime(2020, 2, 7, 17)

        activity_to_mark_as_duplicate = Activity.query.filter(
            Activity.user_time == activity_to_mark_as_duplicate_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        additional_db_changes = []
        for team_mate in self.team:
            activity_data = dict(
                type=activity_to_mark_as_duplicate.type,
                submitter_id=self.team_leader.id,
                user_id=team_mate.id,
                user_time=activity_to_mark_as_duplicate_time,
                event_time=activity_to_mark_as_duplicate_time,
                mission_id=activity_to_mark_as_duplicate.mission_id,
                dismiss_type=None,
            )
            additional_db_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=activity_data,
                    after={
                        **activity_data,
                        "dismiss_type": ActivityDismissType.NO_ACTIVITY_SWITCH,
                        "dismissed_at": cancel_time,
                        "dismiss_author_id": self.team_leader.id,
                    },
                )
            )

        self._cancel_or_edit_activity_as_team_leader(
            activity_to_cancel_user_time,
            cancel_time,
            additional_db_changes=additional_db_changes,
        )

    def test_cancel_activity_handle_complex_neighbour_inconsistencies(self):
        """ We are cancelling all the activities of the day following the 12:13pm break

        The end of the day should be set to 12:13pm after the cancel
        """
        mission = self.test_log_standard_mission()

        activity_to_cancel_user_time = datetime(2020, 2, 7, 12, 53)
        activity_to_revise_time = datetime(2020, 2, 7, 12, 13)
        activity_to_mark_as_duplicate_time = datetime(2020, 2, 7, 16)

        cancel_time = datetime(2020, 2, 7, 17)

        activity_to_mark_as_duplicate = Activity.query.filter(
            Activity.user_time == activity_to_mark_as_duplicate_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        additional_db_changes = []
        for team_mate in self.team:
            activity_data = dict(
                type=activity_to_mark_as_duplicate.type,
                submitter_id=self.team_leader.id,
                user_id=team_mate.id,
                user_time=activity_to_mark_as_duplicate_time,
                event_time=activity_to_mark_as_duplicate_time,
                mission_id=activity_to_mark_as_duplicate.mission_id,
                dismiss_type=None,
            )
            additional_db_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=activity_data,
                    after={
                        **activity_data,
                        "dismiss_type": ActivityDismissType.NO_ACTIVITY_SWITCH,
                        "dismissed_at": cancel_time,
                        "dismiss_author_id": self.team_leader.id,
                    },
                )
            )
            activity_to_revise = Activity.query.filter(
                Activity.user_time == activity_to_revise_time,
                Activity.user_id == team_mate.id,
            ).one()
            additional_db_changes.append(
                DBEntryUpdate(
                    model=Activity,
                    before=None,
                    after=dict(
                        type=ActivityType.REST,
                        user_id=team_mate.id,
                        submitter_id=self.team_leader.id,
                        mission_id=mission["id"],
                        revisee_id=activity_to_revise.id,
                    ),
                )
            )

        self._cancel_or_edit_activity_as_team_leader(
            activity_to_cancel_user_time,
            cancel_time,
            additional_db_changes=additional_db_changes,
        )

    def test_cancel_lone_activity(self):
        """ We are cancelling the single activity of a given mission

        The cancel should remove the mission end as well
        """
        lone_activity_time = datetime(2020, 2, 7, 6)
        mission = self.begin_mission(lone_activity_time)
        mission_end_time = datetime(2020, 2, 7, 8)

        make_authenticated_request(
            time=mission_end_time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.end_mission,
            variables=dict(
                mission_id=mission["id"], event_time=mission_end_time
            ),
        )

        team_mate = self.team_mates[0]
        cancel_time = datetime(2020, 2, 7, 10)

        mission_end_data = dict(
            user_id=team_mate.id,
            submitter_id=self.team_leader.id,
            event_time=mission_end_time,
            user_time=mission_end_time,
            type=ActivityType.REST,
        )
        additional_db_changes = [
            DBEntryUpdate(
                model=Activity,
                before=mission_end_data,
                after={
                    **mission_end_data,
                    "dismiss_type": ActivityDismissType.BREAK_OR_REST_AS_STARTING_ACTIVITY,
                    "dismissed_at": cancel_time,
                    "dismiss_author_id": team_mate.id,
                },
            )
        ]
        self._cancel_or_edit_activity_as_simple_member(
            team_mate,
            lone_activity_time,
            cancel_time,
            additional_db_changes=additional_db_changes,
        )

    def test_edit_activity_cannot_exceed_mission_bounds(self):
        """ Check that an activity revision cannot lead to overlapping missions

        """
        self.test_log_standard_mission(datetime(2020, 2, 7))
        self.test_log_standard_mission(datetime(2020, 2, 8))

        revision_time = datetime(2020, 2, 8, 17)
        revised_activity_time = datetime(
            2020, 2, 8, 6
        )  # The first activity of the second day

        revised_activity = Activity.query.filter(
            Activity.user_time == revised_activity_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        make_authenticated_request(
            time=revision_time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activity_id=revised_activity.id,
                event_time=revision_time,
                dismiss=False,
                user_time=datetime(2020, 2, 7, 15),  # During the first mission
            ),
            request_should_fail_with=True,
        )

    def test_cancel_multiple_activities_by_multiple_cancellors(self):
        """ We are cancelling some activities for the whole team, after one of the team mates did the cancellation on his part.

        The new cancel should proceed for the other team mates
        """
        self.test_log_standard_mission()
        team_mate = self.team_mates[0]

        activity_to_cancel_user_time = datetime(2020, 2, 7, 9, 30)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate, activity_to_cancel_user_time, datetime(2020, 2, 7, 17)
        )

        self._cancel_or_edit_activity_as_team_leader(
            activity_to_cancel_user_time,
            datetime(2020, 2, 7, 17, 30),
            exclude_team_mates=[team_mate],
        )
