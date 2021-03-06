from contextlib import contextmanager

from app import app, db
from app.domain.permissions import can_user_log_on_mission_at, company_admin_at
from app.helpers.errors import (
    AuthorizationError,
    OverlappingMissionsError,
    InvalidParamsError,
    MissionAlreadyValidatedByAdminError,
    MissionAlreadyValidatedByUserError,
)
from app.models.activity import Activity
from app.models import Mission, ActivityVersion
from app.models.mission_end import MissionEnd


def check_event_time_is_not_in_the_future(
    event_time, reception_time, event_time_name
):
    if (
        event_time
        and event_time - reception_time
        >= app.config["MAXIMUM_TIME_AHEAD_FOR_EVENT"]
    ):
        raise InvalidParamsError(
            f"{event_time_name} is in the future by {event_time - reception_time}"
        )


def check_mission_overlaps(user, mission):
    mission_activities = mission.activities_for(user)

    if len(mission_activities) == 0:
        return

    mission_start = mission_activities[0].start_time
    mission_end = mission_activities[-1].end_time
    # 1. Check that the mission period is not overlapping with other ones

    ## 1a. No activity from another mission should be located within the mission period
    existing_conflicting_mission_activity = (
        user.query_activities_with_relations(
            start_time=mission_start,
            end_time=mission_end,
            include_mission_relations=False,
        )
        .filter(Activity.mission_id != mission.id)
        .first()
    )
    if (
        existing_conflicting_mission_activity
        and existing_conflicting_mission_activity.end_time != mission_start
    ):
        raise OverlappingMissionsError(
            f"Mission cannot overlap with mission {existing_conflicting_mission_activity.mission_id} for the user.",
            conflicting_mission=Mission.query.get(
                existing_conflicting_mission_activity.mission_id
            ),
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


def check_logging_permissions_at(submitter, user, mission, time):
    if not mission or not can_user_log_on_mission_at(submitter, mission, time):
        raise AuthorizationError(
            "Actor is not authorized to log on this mission at this time."
        )

    if not user or not can_user_log_on_mission_at(user, mission, time):
        raise AuthorizationError(
            f"Actor is not authorized to log for this user."
        )


def check_mission_still_open_for_activities_edition(
    submitter, mission, user, reception_time
):
    # If a company admin validated the mission, it becomes read-only for everyone
    if any(
        [
            v.is_admin and (not v.user_id or v.user_id == user.id)
            for v in mission.validations
        ]
    ):
        raise MissionAlreadyValidatedByAdminError()

    # If the user validated the mission, only himself or a company admin can edit his data
    if (
        any([v.submitter_id == user.id for v in mission.validations])
        and submitter.id != user.id
        and not company_admin_at(submitter, mission.company_id, reception_time)
    ):
        raise MissionAlreadyValidatedByUserError()


@contextmanager
def handle_activities_update(
    submitter,
    user,
    mission,
    reception_time,
    start_time,
    end_time,
    bypass_check=False,
    reopen_mission_if_needed=True,
):
    # 1. Check that start time and end time are not ahead in the future
    check_event_time_is_not_in_the_future(
        start_time, reception_time, "Start time"
    )
    check_event_time_is_not_in_the_future(end_time, reception_time, "End time")

    # 2. Assess whether the event submitter is authorized to log for the user and the mission
    check_logging_permissions_at(submitter, user, mission, start_time)
    if end_time:
        check_logging_permissions_at(submitter, user, mission, end_time)

    # 2b. Check that the mission is still open for edition, at least for the user
    check_mission_still_open_for_activities_edition(
        submitter, mission, user, reception_time
    )

    # 3. Do the stuff
    yield

    if reopen_mission_if_needed and not end_time:
        existing_mission_end = MissionEnd.query.filter(
            MissionEnd.user_id == user.id, MissionEnd.mission_id == mission.id
        ).one_or_none()

        if existing_mission_end:
            db.session.delete(existing_mission_end)

    if not bypass_check:
        # 4. Flush to check db constraints
        db.session.flush()

        # 5. Check that the created activity didn't introduce inconsistencies in the timeline of missions :
        check_mission_overlaps(user, mission)


def log_activity(
    submitter,
    user,
    mission,
    type,
    reception_time,
    start_time,
    end_time=None,
    context=None,
    bypass_check=False,
):

    with handle_activities_update(
        submitter,
        user,
        mission,
        reception_time,
        start_time,
        end_time,
        bypass_check=bypass_check,
    ):
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
            version=1,
            submitter=submitter,
        )
        db.session.add(activity)
        db.session.add(version)
        return activity
