from app import app, db
from app.domain.log_events import check_whether_event_should_be_logged
from app.domain.permissions import (
    can_submitter_log_for_user,
    can_submitter_log_on_mission,
)
from app.helpers.authentication import AuthorizationError
from app.models.activity import ActivityType, Activity, ActivityDismissType
from app.models import User


def resolve_driver(submitter, driver):
    if not driver:
        return None
    driver_id = driver.get("id")
    if driver_id:
        return User.query.get(driver_id)
    else:
        return User.query.filter(
            User.company_id == submitter.company_id,
            User.first_name == driver.get("first_name"),
            User.last_name == driver.get("last_name"),
        ).one_or_none()


def log_group_activity(
    submitter, type, event_time, user_time, mission, driver=None, comment=None
):
    for user in mission.team_at(user_time):
        log_activity(
            type=type,
            event_time=event_time,
            mission=mission,
            user_time=user_time,
            user=user,
            submitter=submitter,
            driver=driver,
            comment=comment,
        )


def _check_and_delete_corrected_log(user, user_time):
    latest_activity_log = user.current_activity
    if latest_activity_log:
        if latest_activity_log.user_time >= user_time:
            app.logger.warn("Activity event is revising previous history")
        elif (
            user_time - latest_activity_log.user_time
            < app.config["MINIMUM_ACTIVITY_DURATION"]
        ):
            app.logger.info(
                "Event time is close to previous logs, deleting these"
            )
            if latest_activity_log.id is not None:
                db.session.delete(latest_activity_log)
            else:
                db.session.expunge(latest_activity_log)
            # This is a dirty hack to have SQLAlchemy immediately propagate object deletion to parent relations
            latest_activity_log.dismissed_at = True


def check_activity_sequence_in_mission_and_handle_duplicates(
    user, mission, event_time
):
    mission_activities = mission.activities_for(user)

    if len(mission_activities) == 0:
        return

    mission_activity_times = [a.user_time for a in mission_activities]
    mission_time_range = (
        mission_activity_times[0],
        mission_activity_times[-1],
    )

    # 1. Check that the mission period is not overlapping with other ones
    for a in user.acknowledged_activities:
        if (
            mission_time_range[0] <= a.user_time <= mission_time_range[1]
            and a.mission != mission
        ):
            raise ValueError(
                f"The missions {mission} and {a.mission} are overlapping for {user}, which can't happen"
            )

    # 2. Check that there are no two activities with the same user time
    if not len(set(mission_activities)) == len(mission_activities):
        raise ValueError(
            f"{mission} contains two activities with the same start time"
        )

    # 3. Check if the mission contains a REST activity then it is at the last time position
    rest_activities = [
        a for a in mission_activities if a.type == ActivityType.REST
    ]
    if len(rest_activities) > 1:
        raise ValueError(
            f"Cannot end {mission} for {user} because it is already ended"
        )
    if (
        len(rest_activities) == 1
        and rest_activities[0].user_time != mission_time_range[1]
    ):
        raise ValueError(
            f"{mission} for {user} cannot have a normal activity after the mission end"
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
            if (
                next_activity.type == ActivityType.SUPPORT
                and next_activity.driver != activity.driver
            ):
                next_activity.is_driver_switch = True
                activity_idx += 1
            else:
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
    event_time,
    user_time,
    driver=None,
    comment=None,
    bypass_check=False,
):
    try:
        return _log_activity(
            submitter,
            user,
            mission,
            type,
            event_time,
            user_time,
            driver,
            comment,
            bypass_check,
        )
    except Exception as e:
        # If the activity log fails for a team mate we want it to be non blocking (the main activity should be logged for instance)
        if submitter != user:
            return
        raise e


def _log_activity(
    submitter,
    user,
    mission,
    type,
    event_time,
    user_time,
    driver=None,
    comment=None,
    bypass_check=False,
):
    if type == ActivityType.DRIVE:
        # Default to marking the submitter as driver if no driver is provided
        if (driver is None and user == submitter) or user == driver:
            type = ActivityType.DRIVE
        else:
            type = ActivityType.SUPPORT

    # 1. Check that event :
    # - is not ahead in the future
    # - was not already processed
    check_whether_event_should_be_logged(
        user=user,
        submitter=submitter,
        mission=mission,
        event_time=event_time,
        type=type,
        user_time=user_time,
        event_history=user.activities,
    )

    # 2. Assess whether the event submitter is authorized to log for the user and the mission
    if not can_submitter_log_on_mission(submitter, mission):
        raise AuthorizationError(
            f"The user is not authorized to log for this mission"
        )

    if not can_submitter_log_for_user(submitter, user):
        raise AuthorizationError(f"Event is submitted from unauthorized user")

    # 3. Quick correction mechanics : if it's two real-time logs in succession, delete the first one
    is_revision = event_time != user_time
    if not is_revision:
        _check_and_delete_corrected_log(user, user_time)

    # 4. Properly write the activity to the DB
    activity = Activity(
        type=type,
        event_time=event_time,
        mission=mission,
        user_time=user_time,
        user=user,
        submitter=submitter,
        driver=driver,
        creation_comment=comment,
    )
    db.session.add(activity)

    # 5. Check that the created activity didn't introduce inconsistencies in the timeline :
    # - the mission period is not overlapping with other mission periods
    # - the mission activity sequence is consistent (end event must be in last position)
    # - no successive activities with the same type
    if not bypass_check:
        check_activity_sequence_in_mission_and_handle_duplicates(
            user, mission, event_time
        )

    return activity
