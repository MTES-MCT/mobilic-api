from app import db
from app.domain.log_events import get_response_if_event_should_not_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.models import Expenditure
from app.models.event import EventBaseValidationStatus


def log_group_expenditure(submitter, users, type, event_time, reception_time):
    for user in users:
        log_expenditure(
            type=type,
            event_time=event_time,
            reception_time=reception_time,
            user=user,
            submitter=submitter,
        )


def log_expenditure(submitter, user, type, event_time, reception_time):
    response_if_event_should_not_be_logged = get_response_if_event_should_not_be_logged(
        user=user,
        submitter=submitter,
        event_time=event_time,
        reception_time=reception_time,
        type=type,
        event_history=user.expenditures,
    )
    if response_if_event_should_not_be_logged:
        return

    expenditure = Expenditure(
        type=type,
        event_time=event_time,
        reception_time=reception_time,
        user=user,
        company_id=submitter.company_id,
        submitter=submitter,
        validation_status=EventBaseValidationStatus.PENDING
        if can_submitter_log_for_user(submitter, user)
        else EventBaseValidationStatus.UNAUTHORIZED_SUBMITTER,
    )
    db.session.add(expenditure)
