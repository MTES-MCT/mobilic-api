from datetime import datetime

from app import db
from app.domain.log_activities import EventLogError, can_submitter_log_for_user
from app.helpers.time import from_timestamp
from app.models import Expenditure
from app.models.event import EventBaseValidationStatus


def log_group_expenditure(
    submitter, company, users, type, event_time,
):
    return [
        log_expenditure(
            type=type,
            event_time=from_timestamp(event_time),
            user=user,
            company=company,
            submitter=submitter,
        )
        for user in users
    ]


def log_expenditure(
    submitter, user, company, type, event_time,
):
    if not submitter or not user or not company:
        return EventLogError

    reception_time = datetime.now()

    if event_time >= reception_time:
        return EventLogError

    already_existing_logs_for_expenditure = [
        expenditure
        for expenditure in user.expenditures
        if expenditure.event_time == event_time
        and expenditure.type == type
        and expenditure.submitter == submitter
        and expenditure.company == company
    ]

    if len(already_existing_logs_for_expenditure) > 0:
        return already_existing_logs_for_expenditure[0]

    expenditure = Expenditure(
        type=type,
        event_time=event_time,
        reception_time=reception_time,
        user=user,
        company=company,
        submitter=submitter,
        validation_status=EventBaseValidationStatus.PENDING
        if can_submitter_log_for_user(submitter, user, company)
        else EventBaseValidationStatus.UNAUTHORIZED_SUBMITTER,
    )
    db.session.add(expenditure)
    return expenditure
