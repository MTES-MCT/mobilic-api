from sqlalchemy.exc import InvalidRequestError

from app import app, db
from app.domain.log_events import check_whether_event_should_be_logged
from app.domain.permissions import can_user_log_on_mission_at
from app.helpers.errors import (
    AuthorizationError,
    OverlappingMissionsError,
    InvalidParamsError,
    MissionAlreadyEndedError,
    SimultaneousActivitiesError,
    NonContiguousActivitySequenceError,
)
from app.models.activity import ActivityType, Activity, ActivityDismissType
from app.models import Mission


def check_activity_sequence_in_mission_and_handle_duplicates(
    user, mission, event_time
):
    try:
        # Send pending activities to the DB to check simultaneity constraints
        db.session.flush()
    except Exception as e:
        raise SimultaneousActivitiesError()

    mission_activities = mission.activities_for(user)

    if len(mission_activities) == 0:
        return

    mission_activity_times = [a.start_time for a in mission_activities]
    mission_time_range = (
        mission_activity_times[0],
        mission_activity_times[-1],
    )

    # 1. Check that the mission period is not overlapping with other ones

    ## 1a. No activity from another mission should be located within the mission period
    for a in user.query_activities_with_relations(
        start_time=mission_time_range[0], end_time=mission_time_range[1]
    ):
        a_mission_id = a.mission_id if a.mission_id else a.mission.id
        if (
            mission_time_range[0] <= a.start_time <= mission_time_range[1]
            and a_mission_id != mission.id
        ):
            raise OverlappingMissionsError(
                f"Mission cannot overlap with mission {a.mission_id} for the user.",
                conflicting_mission=Mission.query.get(a.mission_id),
            )

    ## 1b. Conversely the mission period should not be contained within another mission period
    latest_activity_before_mission_start = user.latest_acknowledged_activity_before(
        mission_time_range[0]
    )
    if (
        latest_activity_before_mission_start
        and latest_activity_before_mission_start.type != ActivityType.REST
        and latest_activity_before_mission_start.mission_id != mission.id
    ):
        raise OverlappingMissionsError(
            f"Mission cannot overlap with mission {latest_activity_before_mission_start.mission_id} for the user.",
            conflicting_mission=Mission.query.get(
                latest_activity_before_mission_start.mission_id
            ),
        )

    # 2. Check that there are no two activities with the same user time
    if not len(set(mission_activity_times)) == len(mission_activity_times):
        raise SimultaneousActivitiesError()

    # 3. Check if the mission contains a REST activity then it is at the last time position
    rest_activities = [
        a for a in mission_activities if a.type == ActivityType.REST
    ]
    if len(rest_activities) > 1:
        raise MissionAlreadyEndedError(
            f"Mission is already ended for user",
            mission_end=rest_activities[0],
        )
    if (
        len(rest_activities) == 1
        and rest_activities[0].start_time != mission_time_range[1]
    ):
        raise MissionAlreadyEndedError(
            f"User cannot have a new activity after the mission end",
            mission_end=rest_activities[0],
        )

    # 4. Fix eventual duplicates
    activity_idx = -1
    next_activity_idx = 0
    while activity_idx < len(
        mission_activities
    ) - 1 and next_activity_idx < len(mission_activities):
        activity = (
            mission_activities[activity_idx] if activity_idx >= 0 else None
        )
        next_activity = mission_activities[next_activity_idx]

        if activity_idx == next_activity_idx:
            next_activity_idx += 1
        elif activity and activity.is_dismissed:
            activity_idx += 1
        elif next_activity.is_dismissed:
            next_activity_idx += 1

        elif not activity and next_activity.type in [
            ActivityType.BREAK,
            ActivityType.REST,
        ]:
            next_activity.dismiss(
                ActivityDismissType.BREAK_OR_REST_AS_STARTING_ACTIVITY,
                event_time,
            )
            next_activity_idx += 1

        elif activity and activity.type == next_activity.type:
            next_activity.dismiss(
                ActivityDismissType.NO_ACTIVITY_SWITCH, event_time,
            )
            next_activity_idx += 1

        elif (
            activity
            and activity.type == ActivityType.BREAK
            and next_activity.type == ActivityType.REST
        ):
            activity.revise(event_time, type=ActivityType.REST)
            next_activity.dismiss(
                ActivityDismissType.NO_ACTIVITY_SWITCH, event_time
            )
            break

        else:
            activity_idx += 1
            next_activity_idx += 1


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

    # 1. Check that event :
    # - is not ahead in the future
    # - was not already processed
    if (
        end_time
        and end_time - reception_time
        >= app.config["MAXIMUM_TIME_AHEAD_FOR_EVENT"]
    ):
        raise InvalidParamsError(
            f"End time was set in the future by {end_time - reception_time} : activity will not be logged"
        )

    if not end_time:
        check_whether_event_should_be_logged(
            submitter_id=submitter.id,
            reception_time=reception_time,
            event_time=start_time,
        )

    # 2. Assess whether the event submitter is authorized to log for the user and the mission
    if not mission or not can_user_log_on_mission_at(
        submitter, mission, start_time
    ):
        raise AuthorizationError(
            "Actor is not authorized to log on this mission."
        )

    if not user or not can_user_log_on_mission_at(user, mission, start_time):
        raise AuthorizationError(
            f"Actor is not authorized to log for this user."
        )

    # 3. If it's a revision and if an end time was specified we need to potentially correct multiple activities
    if end_time:
        activities = mission.activities_for(user)
        overriden_activities = [
            a for a in activities if start_time <= a.start_time <= end_time
        ]
        if overriden_activities:
            activity_to_shift = overriden_activities[-1]
            activities_to_cancel = overriden_activities[:-1]
            for a in activities_to_cancel:
                a.dismiss(
                    ActivityDismissType.USER_CANCEL,
                    dismiss_time=reception_time,
                )
            if end_time != activity_to_shift.start_time:
                activity_to_shift.revise(reception_time, start_time=end_time)
        else:
            activities_before = [
                a for a in activities if a.start_time < start_time
            ]
            if activities_before:
                activity_immediately_before = activities_before[-1]
                log_activity(
                    submitter,
                    user,
                    mission,
                    activity_immediately_before.type,
                    reception_time,
                    start_time=end_time,
                    end_time=None,
                    context=activity_immediately_before.context,
                    bypass_check=True,
                )
            else:
                activities_after = [
                    a for a in activities if a.start_time > end_time
                ]
                if activities_after:
                    raise NonContiguousActivitySequenceError(
                        "Logging the activity would create a hole in the time series."
                    )
                else:
                    raise InvalidParamsError(
                        "You are trying to set an end time for the current activity."
                    )

    # 4. Properly write the activity to the DB
    activity = Activity(
        type=type,
        reception_time=reception_time,
        mission=mission,
        start_time=start_time,
        user=user,
        submitter=submitter,
        context=context,
    )
    db.session.add(activity)

    # 5. Check that the created activity didn't introduce inconsistencies in the timeline :
    # - the mission period is not overlapping with other mission periods
    # - the mission activity sequence is consistent (end event must be in last position)
    # - no successive activities with the same type
    if not bypass_check:
        try:
            check_activity_sequence_in_mission_and_handle_duplicates(
                user, mission, reception_time
            )
        except Exception as e:
            try:
                db.session.expunge(activity)
            except InvalidRequestError:
                pass
            raise e

    return activity
