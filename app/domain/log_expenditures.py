from app import db
from app.domain.log_events import get_response_if_event_should_not_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.helpers.time import from_timestamp
from app.models import Expenditure
from app.models.event import EventBaseValidationStatus


def log_group_expenditure(
    submitter, company, users, type, event_time, reception_time
):
    return [
        log_expenditure(
            type=type,
            event_time=from_timestamp(event_time),
            reception_time=reception_time,
            user=user,
            company=company,
            submitter=submitter,
        )
        for user in users
    ]


def log_expenditure(
    submitter, user, company, type, event_time, reception_time
):
    response_if_event_should_not_be_logged = get_response_if_event_should_not_be_logged(
        user=user,
        submitter=submitter,
        company=company,
        event_time=event_time,
        reception_time=reception_time,
        type=type,
        event_history=user.expenditures,
    )
    if response_if_event_should_not_be_logged:
        return response_if_event_should_not_be_logged

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
