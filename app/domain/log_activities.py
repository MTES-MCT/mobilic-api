from app import app, db
from app.domain.log_events import get_response_if_event_should_not_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.helpers.time import local_to_utc
from app.models.activity import (
    ActivityTypes,
    Activity,
    ActivityContext,
)


def log_group_activity(
    submitter,
    users,
    type,
    event_time,
    reception_time,
    driver_idx,
    vehicle_registration_number,
    mission,
):
    activities_per_user = {user: type for user in users}
    if len(users) > 1:
        if type == ActivityTypes.DRIVE:
            driver = users[driver_idx] if driver_idx is not None else None
            for user in users:
                if user == driver:
                    activities_per_user[user] = ActivityTypes.DRIVE
                else:
                    activities_per_user[user] = ActivityTypes.SUPPORT

    for user in users:
        log_activity(
            type=activities_per_user[user],
            event_time=event_time,
            reception_time=reception_time,
            user=user,
            submitter=submitter,
            vehicle_registration_number=vehicle_registration_number,
            mission=mission,
            team=[u.id for u in users],
            driver_idx=driver_idx,
        )


def _get_activity_context(
    submitter, user, type, event_time, team, driver_idx,
):
    if not can_submitter_log_for_user(submitter, user):
        app.logger.warn("Event is submitted from unauthorized user")
        return ActivityContext.UNAUTHORIZED_SUBMITTER

    latest_activity_log = user.current_acknowledged_activity
    if latest_activity_log:
        if latest_activity_log.event_time >= event_time:
            app.logger.warn("Event is conflicting with previous logs")
            return ActivityContext.CONFLICTING_WITH_HISTORY
        else:
            if (
                event_time - latest_activity_log.event_time
                < app.config["MINIMUM_ACTIVITY_DURATION"]
            ):
                app.logger.info(
                    "Event time is close to previous logs, deleting these"
                )
                if latest_activity_log.id is not None:
                    db.session.delete(latest_activity_log)
                else:
                    db.session.expunge(latest_activity_log)
                user_activities = user.acknowledged_activities
                latest_activity_log = (
                    user_activities[-2] if len(user_activities) >= 2 else None
                )
    if not latest_activity_log and type == ActivityTypes.REST:
        return ActivityContext.NO_ACTIVITY_SWITCH
    if latest_activity_log and latest_activity_log.type == type:
        if (
            type == ActivityTypes.SUPPORT
            and team[driver_idx]
            != latest_activity_log.team[latest_activity_log.driver_idx]
        ):
            return ActivityContext.DRIVER_SWITCH
        return ActivityContext.NO_ACTIVITY_SWITCH
    if (
        latest_activity_log
        and latest_activity_log.type == ActivityTypes.REST
        and local_to_utc(latest_activity_log.event_time).date()
        == local_to_utc(event_time).date()
    ):
        latest_activity_log.type = ActivityTypes.BREAK
        db.session.add(latest_activity_log)
    if (
        latest_activity_log
        and latest_activity_log.type == ActivityTypes.BREAK
        and type == ActivityTypes.REST
    ):
        latest_activity_log.type = ActivityTypes.REST
        db.session.add(latest_activity_log)
        return ActivityContext.NO_ACTIVITY_SWITCH

    return None


def log_activity(
    submitter,
    user,
    type,
    event_time,
    reception_time,
    vehicle_registration_number,
    mission,
    team,
    driver_idx,
):
    response_if_event_should_not_be_logged = get_response_if_event_should_not_be_logged(
        user=user,
        submitter=submitter,
        event_time=event_time,
        reception_time=reception_time,
        type=type,
        event_history=user.activities,
    )
    if response_if_event_should_not_be_logged:
        return

    context = _get_activity_context(
        submitter=submitter,
        user=user,
        type=type,
        event_time=event_time,
        team=team,
        driver_idx=driver_idx,
    )

    activity = Activity(
        type=type,
        event_time=event_time,
        reception_time=reception_time,
        user=user,
        company_id=submitter.company_id,
        submitter=submitter,
        context=context,
        vehicle_registration_number=vehicle_registration_number,
        mission=mission,
        team=team,
        driver_idx=driver_idx,
    )
    db.session.add(activity)
