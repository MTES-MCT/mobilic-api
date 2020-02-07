from datetime import timedelta, datetime

from app import app, db
from app.helpers.time import from_timestamp
from app.models.activity import (
    ActivityTypes,
    Activity,
    ActivityValidationStatus,
)


class ActivityLogError:
    pass


def log_group_activity(submitter, company, users, type, event_time, driver):
    activities_per_user = {user: type for user in users}
    if type == ActivityTypes.DRIVE:
        for user in users:
            if user == driver:
                activities_per_user[user] = ActivityTypes.DRIVE
            else:
                activities_per_user[user] = ActivityTypes.SUPPORT

    return [
        log_activity(
            type=activities_per_user[user],
            event_time=from_timestamp(event_time),
            user=user,
            company=company,
            submitter=submitter,
        )
        for user in users
    ]


def log_activity(submitter, user, company, type, event_time):
    if not submitter or not user or not company:
        return ActivityLogError

    reception_time = datetime.now()

    if event_time >= reception_time:
        return ActivityLogError

    already_existing_logs_for_activity = [
        activity
        for activity in user.activities
        if activity.event_time == event_time
        and activity.type == type
        and activity.submitter == submitter
        and activity.company == company
    ]

    if len(already_existing_logs_for_activity) > 0:
        return already_existing_logs_for_activity[0]

    validation_status = ActivityValidationStatus.PENDING

    if not _can_submitter_log_for_user(submitter, user, company):
        validation_status = ActivityValidationStatus.UNAUTHORIZED_SUBMITTER
    else:
        latest_activity_log = user.current_acknowledged_activity
        if latest_activity_log.event_time >= event_time:
            validation_status = (
                ActivityValidationStatus.CONFLICTING_WITH_HISTORY
            )
        else:
            if event_time - latest_activity_log.event_time < timedelta(
                minutes=app.config["MINIMUM_ACTIVITY_DURATION"]
            ):
                db.session.delete(latest_activity_log)
                latest_activity_log = user.current_acknowledged_activity
            if latest_activity_log.type == type:
                validation_status = ActivityValidationStatus.NO_ACTIVITY_SWITCH

    return Activity(
        type=type,
        event_time=event_time,
        reception_time=reception_time,
        user=user,
        company=company,
        submitter=submitter,
        validation_status=validation_status,
    )


def _can_submitter_log_for_user(
    submitter, user, company,
):
    return submitter.company_id == user.company_id == company.id
