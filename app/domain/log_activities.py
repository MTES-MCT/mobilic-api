from app import app, db
from app.domain.log_events import get_response_if_event_should_not_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.models.activity import (
    ActivityTypes,
    Activity,
    ActivityValidationStatus,
)


def log_group_activity(
    submitter,
    company,
    users,
    type,
    event_time,
    reception_time,
    driver,
    vehicle_registration_number,
    mission,
):
    activities_per_user = {user: type for user in users}
    if len(users) > 1:
        if type == ActivityTypes.DRIVE:
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
            company=company,
            submitter=submitter,
            vehicle_registration_number=vehicle_registration_number,
            mission=mission,
            team=[u.id for u in users],
        )


def log_activity(
    submitter,
    user,
    company,
    type,
    event_time,
    reception_time,
    vehicle_registration_number,
    mission,
    team,
):
    response_if_event_should_not_be_logged = get_response_if_event_should_not_be_logged(
        user=user,
        submitter=submitter,
        company=company,
        event_time=event_time,
        reception_time=reception_time,
        type=type,
        event_history=user.activities,
    )
    if response_if_event_should_not_be_logged:
        return

    validation_status = ActivityValidationStatus.PENDING

    if not can_submitter_log_for_user(submitter, user, company):
        validation_status = ActivityValidationStatus.UNAUTHORIZED_SUBMITTER
    else:
        latest_activity_log = user.current_acknowledged_activity
        if latest_activity_log:
            if latest_activity_log.event_time >= event_time:
                validation_status = (
                    ActivityValidationStatus.CONFLICTING_WITH_HISTORY
                )
            else:
                if (
                    event_time - latest_activity_log.event_time
                    < app.config["MINIMUM_ACTIVITY_DURATION"]
                ):
                    print("Deleting previous activity")
                    if latest_activity_log.id is not None:
                        db.session.delete(latest_activity_log)
                    else:
                        db.session.expunge(latest_activity_log)
                    user_activities = user.acknowledged_activities
                    latest_activity_log = (
                        user_activities[-2]
                        if len(user_activities) >= 2
                        else None
                    )
                if latest_activity_log and latest_activity_log.type == type:
                    validation_status = (
                        ActivityValidationStatus.NO_ACTIVITY_SWITCH
                    )

    activity = Activity(
        type=type,
        event_time=event_time,
        reception_time=reception_time,
        user=user,
        company=company,
        submitter=submitter,
        validation_status=validation_status,
        vehicle_registration_number=vehicle_registration_number,
        mission=mission,
        team=team,
    )
    db.session.add(activity)
