from datetime import datetime
from random import randint

from app.models import Mission
from app.models.activity import (
    ActivityType,
    Activity,
)
from app.tests.helpers import (
    DBEntryUpdate,
    make_authenticated_request,
    test_db_changes,
    ApiRequests,
    ForeignKey,
)

from app.tests.test_log_activities import TestLogActivities


class TestEditActivities(TestLogActivities):
    def _cancel_or_edit_activity_as_team_leader(
        self,
        activity_time,
        edit_time,
        new_activity_time=None,
        new_activity_end_time=None,
        exclude_team_mate_ids=None,
        additional_db_changes=None,
    ):
        exclude_team_mate_ids = exclude_team_mate_ids or []

        expected_changes = additional_db_changes or {}
        if type(expected_changes) is list:
            expected_changes = {
                str(idx): item for idx, item in enumerate(expected_changes)
            }
        for team_mate_id in self.team_ids:
            activity_to_edit = Activity.query.filter(
                Activity.start_time == activity_time,
                Activity.user_id == team_mate_id,
            ).one()
            if team_mate_id not in exclude_team_mate_ids:
                activity_data = dict(
                    type=activity_to_edit.type,
                    submitter_id=self.team_leader.id,
                    user_id=team_mate_id,
                    start_time=activity_time,
                    end_time=activity_to_edit.end_time,
                    reception_time=activity_time,
                    mission_id=activity_to_edit.mission_id,
                    dismiss_type=None,
                )
                random_id = str(randint(1000, 1000000))
                if new_activity_time or new_activity_end_time:
                    new_activity_data = {**activity_data}
                    if new_activity_time:
                        new_activity_data["start_time"] = new_activity_time
                    if new_activity_end_time:
                        new_activity_data["end_time"] = new_activity_end_time
                    new_activity_data["last_update_time"] = edit_time
                    expected_changes.update(
                        {
                            random_id: DBEntryUpdate(
                                model=Activity,
                                before=activity_data,
                                after=new_activity_data,
                            )
                        }
                    )
                else:
                    expected_changes.update(
                        {
                            random_id: DBEntryUpdate(
                                model=Activity,
                                before=activity_data,
                                after={
                                    **activity_data,
                                    "dismissed_at": edit_time,
                                    "dismiss_author_id": self.team_leader.id,
                                },
                            )
                        }
                    )

        with test_db_changes(
            expected_changes, watch_models=[Activity, Mission]
        ):
            for team_mate_id in self.team_ids:
                activity_to_edit = Activity.query.filter(
                    Activity.start_time == activity_time,
                    Activity.user_id == team_mate_id,
                ).one()
                if team_mate_id not in exclude_team_mate_ids:
                    make_authenticated_request(
                        time=edit_time,
                        submitter_id=self.team_leader.id,
                        query=ApiRequests.edit_activity
                        if (new_activity_time or new_activity_end_time)
                        else ApiRequests.cancel_activity,
                        variables=dict(
                            activity_id=activity_to_edit.id,
                            start_time=new_activity_time,
                            end_time=new_activity_end_time,
                        )
                        if (new_activity_time or new_activity_end_time)
                        else dict(activity_id=activity_to_edit.id),
                    )

    def _cancel_or_edit_activity_as_simple_member(
        self,
        team_mate_id,
        activity_time,
        edit_time,
        new_activity_time=None,
        new_activity_end_time=None,
        additional_db_changes=None,
    ):
        activity_to_edit = Activity.query.filter(
            Activity.start_time == activity_time,
            Activity.user_id == team_mate_id,
        ).one()

        activity_data = dict(
            type=activity_to_edit.type,
            submitter_id=self.team_leader.id,
            user_id=team_mate_id,
            start_time=activity_time,
            end_time=activity_to_edit.end_time,
            reception_time=activity_time,
            mission_id=activity_to_edit.mission_id,
            dismiss_type=None,
        )

        expected_changes = additional_db_changes or {}
        if type(expected_changes) is list:
            expected_changes = {
                str(idx): item for idx, item in enumerate(expected_changes)
            }
        random_id = str(randint(1000, 1000000))

        if new_activity_time or new_activity_end_time:
            new_activity_data = {**activity_data}
            if new_activity_time:
                new_activity_data["start_time"] = new_activity_time
            if new_activity_end_time:
                new_activity_data["end_time"] = new_activity_end_time
            new_activity_data["last_update_time"] = edit_time
            expected_changes.update(
                {
                    random_id: DBEntryUpdate(
                        model=Activity,
                        before=activity_data,
                        after=new_activity_data,
                    )
                }
            )
        else:
            expected_changes.update(
                {
                    random_id: DBEntryUpdate(
                        model=Activity,
                        before=activity_data,
                        after={
                            **activity_data,
                            "dismissed_at": edit_time,
                            "dismiss_author_id": team_mate_id,
                        },
                    )
                }
            )

        with test_db_changes(
            expected_changes, watch_models=[Activity, Mission]
        ):
            make_authenticated_request(
                time=edit_time,
                submitter_id=team_mate_id,
                query=ApiRequests.edit_activity
                if (new_activity_time or new_activity_end_time)
                else ApiRequests.cancel_activity,
                variables=dict(
                    activity_id=activity_to_edit.id,
                    start_time=new_activity_time,
                    end_time=new_activity_end_time,
                )
                if (new_activity_time or new_activity_end_time)
                else dict(activity_id=activity_to_edit.id),
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
            2020, 2, 7, 7
        )  # The second activity of the mission : work
        new_activity_end_time = datetime(2020, 2, 7, 8)
        self._cancel_or_edit_activity_as_team_leader(
            activity_to_edit_time,
            datetime(2020, 2, 7, 17),
            new_activity_end_time=new_activity_end_time,
        )

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
        team_mate_id = self.team_mates[0].id
        self.test_log_standard_mission()

        activity_to_cancel_user_time = datetime(
            2020, 2, 7, 9, 30
        )  # The third activity of the mission : work
        self._cancel_or_edit_activity_as_simple_member(
            team_mate_id,
            activity_to_cancel_user_time,
            datetime(2020, 2, 7, 17),
        )

    def test_edit_activity_as_simple_member(self):
        team_mate_id = self.team_mates[0].id
        self.test_log_standard_mission()

        activity_to_edit_time = datetime(
            2020, 2, 7, 7
        )  # The second activity of the mission : work
        new_activity_end_time = datetime(2020, 2, 7, 8)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate_id,
            activity_to_edit_time,
            datetime(2020, 2, 7, 17),
            new_activity_end_time=new_activity_end_time,
        )

        activity_to_edit_time = datetime(
            2020, 2, 7, 9, 30
        )  # The third activity of the mission : work
        new_activity_time = datetime(2020, 2, 7, 8)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate_id,
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
        team_mate_id = self.team_mates[0].id
        self.test_log_standard_mission()

        first_activity_to_cancel_user_time = datetime(2020, 2, 7, 9, 30)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate_id,
            first_activity_to_cancel_user_time,
            datetime(2020, 2, 7, 17),
        )

        second_activity_to_cancel_user_time = datetime(2020, 2, 7, 6)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate_id,
            second_activity_to_cancel_user_time,
            datetime(2020, 2, 7, 17, 30),
        )

    def test_edit_multiple_activities(self):
        team_mate_id = self.team_mates[0].id
        self.test_log_standard_mission()

        first_activity_to_edit_user_time = datetime(2020, 2, 7, 7)
        first_activity_new_end_time = datetime(2020, 2, 7, 9)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate_id,
            first_activity_to_edit_user_time,
            datetime(2020, 2, 7, 17),
            new_activity_end_time=first_activity_new_end_time,
        )

        first_activity_to_edit_user_time = datetime(2020, 2, 7, 9, 30)
        first_activity_new_time = datetime(2020, 2, 7, 9)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate_id,
            first_activity_to_edit_user_time,
            datetime(2020, 2, 7, 17),
            new_activity_time=first_activity_new_time,
        )

        second_activity_to_edit_user_time = datetime(2020, 2, 7, 6)
        second_activity_new_time = datetime(2020, 2, 7, 6, 30)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate_id,
            second_activity_to_edit_user_time,
            datetime(2020, 2, 7, 17, 30),
            new_activity_time=second_activity_new_time,
        )

    def test_cancel_activity_handle_complex_neighbour_inconsistencies(self):
        """We are cancelling all the activities of the day following the 12:13pm break

        The end of the day should be set to 12:13pm after the cancel
        """
        mission_id = self.test_log_standard_mission()

        activity_to_cancel_user_time = datetime(2020, 2, 7, 12, 53)
        cancel_time = datetime(2020, 2, 7, 17)

        self._cancel_or_edit_activity_as_team_leader(
            activity_to_cancel_user_time,
            cancel_time,
        )

    def test_cancel_lone_activity(self):
        """We are cancelling the single activity of a given mission

        The cancel should remove the mission end as well
        """
        first_team_mate_id = self.team_mates[0].id

        lone_activity_time = datetime(2020, 2, 7, 6)
        mission_id = self.begin_mission(lone_activity_time)
        mission_end_time = datetime(2020, 2, 7, 8)

        for team_mate_id in self.team_ids:
            make_authenticated_request(
                time=mission_end_time,
                submitter_id=self.team_leader.id,
                query=ApiRequests.end_mission,
                variables=dict(
                    mission_id=mission_id,
                    end_time=mission_end_time,
                    user_id=team_mate_id,
                ),
            )

        cancel_time = datetime(2020, 2, 7, 10)

        self._cancel_or_edit_activity_as_simple_member(
            first_team_mate_id,
            lone_activity_time,
            cancel_time,
        )

    def test_edit_activity_cannot_exceed_mission_bounds(self):
        """Check that an activity revision cannot lead to overlapping missions"""
        self.test_log_standard_mission(datetime(2020, 2, 7))
        self.test_log_standard_mission(datetime(2020, 2, 8))

        revision_time = datetime(2020, 2, 8, 17)
        revised_activity_time = datetime(
            2020, 2, 8, 6
        )  # The first activity of the second day

        revised_activity = Activity.query.filter(
            Activity.start_time == revised_activity_time,
            Activity.user_id == self.team_leader.id,
        ).one()

        make_authenticated_request(
            time=revision_time,
            submitter_id=self.team_leader.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activity_id=revised_activity.id,
                start_time=datetime(
                    2020, 2, 7, 15
                ),  # During the first mission
            ),
            request_should_fail_with=True,
        )

    def test_cancel_multiple_activities_by_multiple_cancellors(self):
        """We are cancelling some activities for the whole team, after one of the team mates did the cancellation on his part.

        The new cancel should proceed for the other team mates
        """
        team_mate_id = self.team_mates[0].id

        self.test_log_standard_mission()

        activity_to_cancel_user_time = datetime(2020, 2, 7, 9, 30)
        self._cancel_or_edit_activity_as_simple_member(
            team_mate_id,
            activity_to_cancel_user_time,
            datetime(2020, 2, 7, 17),
        )

        self._cancel_or_edit_activity_as_team_leader(
            activity_to_cancel_user_time,
            datetime(2020, 2, 7, 17, 30),
            exclude_team_mate_ids=[team_mate_id],
        )
