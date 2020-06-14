from flask import g
from app import app, db
from app.domain.log_events import check_whether_event_should_be_logged
from app.domain.permissions import (
    can_submitter_log_for_user,
    can_submitter_log_on_mission,
)
from app.helpers.errors import (
    AuthorizationError,
    OverlappingMissionsError,
    InvalidEventParamsError,
    MissionAlreadyEndedError,
    SimultaneousActivitiesError,
    add_non_blocking_error,
)
from app.models.activity import ActivityType, Activity, ActivityDismissType
from app.models import User, Mission


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
    submitter,
    type,
    event_time,
    user_time,
    mission,
    driver=None,
    comment=None,
    user_end_time=None,
):
    team_at_time = mission.team_at(user_time)
    for user in team_at_time:
        log_activity(
            type=type,
            event_time=event_time,
            mission=mission,
            user_time=user_time,
            user=user,
            submitter=submitter,
            driver=driver,
            comment=comment,
            user_end_time=user_end_time,
        )

    if not team_at_time:
        mission_activities = mission.activities_for(submitter)
        if mission_activities:
            add_non_blocking_error(
                MissionAlreadyEndedError(
                    f"Cannot log activity because mission is already ended",
                    mission_end=mission_activities[-1],
                )
            )


def _check_and_delete_corrected_log(user, user_time):
    latest_activity_log = user.current_activity
    if latest_activity_log:
        if latest_activity_log.user_time >= user_time:
            app.logger.warn(
                "There are more recent activities in the db : the events might have been sent in disorder by the client"
            )
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
        a_mission_id = a.mission_id if a.mission_id else a.mission.id
        if (
            mission_time_range[0] <= a.user_time <= mission_time_range[1]
            and a_mission_id != mission.id
        ):
            raise OverlappingMissionsError(
                f"The missions {mission.id} and {a.mission_id} are overlapping for {user}, which can't happen",
                user=user,
                conflicting_mission=Mission.query.get(a.mission_id),
            )

    # 2. Check that there are no two activities with the same user time
    if not len(set(mission_activities)) == len(mission_activities):
        raise SimultaneousActivitiesError(
            f"{mission} contains two activities with the same start time"
        )

    # 3. Check if the mission contains a REST activity then it is at the last time position
    rest_activities = [
        a for a in mission_activities if a.type == ActivityType.REST
    ]
    if len(rest_activities) > 1:
        raise MissionAlreadyEndedError(
            f"Cannot end {mission} for {user} because it is already ended",
            mission_end=rest_activities[0],
        )
    if (
        len(rest_activities) == 1
        and rest_activities[0].user_time != mission_time_range[1]
    ):
        raise MissionAlreadyEndedError(
            f"{mission} for {user} cannot have a normal activity after the mission end",
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
    user_end_time=None,
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
            user_end_time,
            bypass_check,
        )
    except Exception as e:
        # If the activity log fails for a team mate we want it to be non blocking (the main activity should be logged for instance)
        if submitter.id != user.id:
            app.logger.exception(e)
            add_non_blocking_error(e)
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
    user_end_time=None,
    bypass_check=False,
):
    if type == ActivityType.DRIVE:
        # Default to marking the submitter as driver if no driver is provided
        if (driver is None and user == submitter) or user == driver:
            type = ActivityType.DRIVE
        else:
            type = ActivityType.SUPPORT

    is_revision = event_time != user_time

    # 1. Check that event :
    # - is not ahead in the future
    # - was not already processed
    if (
        user_end_time
        and user_end_time - event_time
        >= app.config["MAXIMUM_TIME_AHEAD_FOR_EVENT"]
    ):
        raise InvalidEventParamsError(
            f"End time was set in the future by {user_end_time - event_time} : will not log"
        )

    if not is_revision or not user_end_time:
        check_whether_event_should_be_logged(
            user_id=user.id,
            submitter_id=submitter.id,
            mission_id=mission.id,
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
    if not is_revision:
        _check_and_delete_corrected_log(user, user_time)

    # 3b. If it's a revision and if an end time was specified we need to potentially correct multiple activities
    if is_revision and user_end_time:
        activities = mission.activities_for(user)
        overriden_activities = [
            a for a in activities if user_time <= a.user_time <= user_end_time
        ]
        if overriden_activities:
            activity_to_shift = overriden_activities[-1]
            activities_to_cancel = overriden_activities[:-1]
            for a in activities_to_cancel:
                a.dismiss(
                    ActivityDismissType.USER_CANCEL, dismiss_time=event_time
                )
            if user_end_time != activity_to_shift.user_time:
                activity_to_shift.revise(event_time, user_time=user_end_time)
        else:
            activities_before = [
                a for a in activities if a.user_time < user_time
            ]
            if activities_before:
                activity_immediately_before = activities_before[-1]
                log_activity(
                    submitter,
                    user,
                    mission,
                    activity_immediately_before.type,
                    event_time,
                    user_time=user_end_time,
                    driver=activity_immediately_before.driver,
                    comment=None,
                    user_end_time=None,
                    bypass_check=True,
                )
            else:
                activities_after = [
                    a for a in activities if a.user_time > user_end_time
                ]
                if activities_after:
                    activity_to_shift = activities_after[0]
                    activity_to_shift.revise(
                        event_time, user_time=user_end_time
                    )
                else:
                    raise InvalidEventParamsError(
                        "You are trying to set an end time for the current activity, this is not allowed"
                    )

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
        try:
            check_activity_sequence_in_mission_and_handle_duplicates(
                user, mission, event_time
            )
        except Exception as e:
            db.session.expunge(activity)
            raise e

    return activity
