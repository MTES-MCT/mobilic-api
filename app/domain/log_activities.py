from contextlib import contextmanager

from app import app, db
from app.domain.permissions import check_actor_can_write_on_mission_over_period
from app.helpers.errors import (
    OverlappingMissionsError,
    UnavailableSwitchModeError,
    ActivityInFutureError,
)
from app.models.activity import Activity
from app.models import Mission, ActivityVersion
from app.models.mission_end import MissionEnd


def check_event_time_is_not_in_the_future(
    event_time, reception_time, event_name
):
    if (
        event_time
        and event_time - reception_time
        >= app.config["MAXIMUM_TIME_AHEAD_FOR_EVENT"]
    ):
        raise ActivityInFutureError(
            event_time,
            reception_time,
            event_name,
            message=f"{event_name} time is in the future by {event_time - reception_time}",
        )


def check_overlaps(user, mission):
    # 1. Flush to check DB overlap constraints
    db.session.flush()

    # 2. Check that the created activity didn't introduce inconsistencies in the timeline of missions
    _check_inter_mission_overlaps(user, mission)


def _check_inter_mission_overlaps(user, mission):
    mission_activities = mission.activities_for(user)

    if len(mission_activities) == 0:
        return

    mission_start = mission_activities[0].start_time
    mission_end = mission_activities[-1].end_time

    # Check that the mission period is not overlapping with other ones
    ## 1. No activity from another mission should be located within the mission period
    other_mission_activities_in_potential_conflict = (
        user.query_activities_with_relations(
            start_time=mission_start,
            end_time=mission_end,
            include_mission_relations=False,
        )
        .filter(Activity.mission_id != mission.id)
        .all()
    )
    for activity in other_mission_activities_in_potential_conflict:
        if not (
            (activity.end_time and activity.end_time <= mission_start)
            or (activity.start_time >= mission_end)
        ):
            raise OverlappingMissionsError(
                f"Mission cannot overlap with mission {activity.mission_id} for the user.",
                conflicting_mission=Mission.query.get(activity.mission_id),
            )

    ## 1b. Conversely the mission period should not be contained within another mission period
    latest_activity_before_mission_start = user.latest_activity_before(
        mission_start
    )
    first_activity_after_mission_end = (
        user.first_activity_after(mission_end) if mission_end else None
    )
    if (
        latest_activity_before_mission_start
        and first_activity_after_mission_end
        and latest_activity_before_mission_start.mission_id
        == first_activity_after_mission_end.mission_id
    ):
        raise OverlappingMissionsError(
            f"Mission cannot overlap with mission {latest_activity_before_mission_start.mission_id} for the user.",
            conflicting_mission=Mission.query.get(
                latest_activity_before_mission_start.mission_id
            ),
        )


@contextmanager
def handle_activities_update(
    submitter,
    user,
    mission,
    reception_time,
    start_time,
    end_time,
    bypass_auth_check=False,
    bypass_overlap_check=False,
    reopen_mission_if_needed=True,
):
    # 1. Check that start time and end time are not ahead in the future
    check_event_time_is_not_in_the_future(start_time, reception_time, "Start")
    check_event_time_is_not_in_the_future(end_time, reception_time, "End")

    # 2. Assess whether the event submitter is authorized to log for the user and the mission
    if not bypass_auth_check:
        check_actor_can_write_on_mission_over_period(
            submitter,
            mission,
            for_user=user,
            start=start_time,
            end=end_time or start_time,
        )
    # 3. Do the stuff
    yield

    if reopen_mission_if_needed and not end_time:
        existing_mission_end = MissionEnd.query.filter(
            MissionEnd.user_id == user.id, MissionEnd.mission_id == mission.id
        ).one_or_none()

        if existing_mission_end:
            db.session.delete(existing_mission_end)

    if not bypass_overlap_check:
        # 4. Check that the new/updated activity is consistent with the timeline for the user
        check_overlaps(user, mission)


def log_activity(
    submitter,
    user,
    mission,
    type,
    reception_time,
    switch_mode,
    start_time,
    end_time=None,
    context=None,
    bypass_overlap_check=False,
    bypass_auth_check=False,
):

    with handle_activities_update(
        submitter,
        user,
        mission,
        reception_time,
        start_time,
        end_time,
        bypass_overlap_check=bypass_overlap_check,
        bypass_auth_check=bypass_auth_check,
    ):
        if switch_mode:
            current_activity = mission.current_activity_at_time_for_user(
                user, start_time
            )
            if current_activity:
                if current_activity.end_time:
                    raise UnavailableSwitchModeError()
                if current_activity.type == type:
                    return current_activity
                if not current_activity.end_time:
                    current_activity.revise(
                        reception_time,
                        bypass_overlap_check=True,
                        bypass_auth_check=True,
                        end_time=start_time,
                    )
        activity = Activity(
            type=type,
            reception_time=reception_time,
            last_update_time=reception_time,
            mission=mission,
            start_time=start_time,
            end_time=end_time,
            user=user,
            submitter=submitter,
        )
        version = ActivityVersion(
            activity=activity,
            reception_time=reception_time,
            start_time=start_time,
            end_time=end_time,
            context=context,
            version_number=1,
            submitter=submitter,
        )
        db.session.add(activity)
        db.session.add(version)
        return activity
