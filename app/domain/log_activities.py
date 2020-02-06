from app.helpers.time import from_timestamp
from app.models.activity import (
    ActivityTypes,
    Activity,
    ActivityValidationStatus,
)


def log_activity(submitter, company, users, activity_type, event_time, driver):
    activities_per_user = {user: activity_type for user in users}
    if activity_type == ActivityTypes.DRIVE:
        for user in users:
            if user == driver:
                activities_per_user[user] = ActivityTypes.DRIVE
            else:
                activities_per_user[user] = ActivityTypes.SUPPORT

    return [
        Activity(
            type=activities_per_user[user],
            event_time=from_timestamp(event_time),
            user=user,
            company=company,
            submitter=submitter,
            validated=ActivityValidationStatus.pending
            if _can_submitter_log_for_user(submitter, user, company)
            else ActivityValidationStatus.UNAUTHORIZED_SUBMITTER,
        )
        for user in users
    ]


def _can_submitter_log_for_user(submitter, user, company):
    return submitter.company_id == user.company_id == company.id
