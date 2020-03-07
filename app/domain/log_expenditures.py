from app import db
from app.domain.log_events import check_whether_event_should_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.models import Expenditure
from app.models.event import DismissType


def log_group_expenditure(submitter, users, type, event_time):
    for user in users:
        log_expenditure(
            type=type, event_time=event_time, user=user, submitter=submitter,
        )


def log_expenditure(submitter, user, type, event_time):
    response_if_event_should_not_be_logged = check_whether_event_should_be_logged(
        user=user,
        submitter=submitter,
        event_time=event_time,
        type=type,
        event_history=user.expenditures,
    )
    if response_if_event_should_not_be_logged:
        return

    expenditure = Expenditure(
        type=type,
        event_time=event_time,
        user=user,
        company_id=submitter.company_id,
        submitter=submitter,
    )
    if not can_submitter_log_for_user(submitter, user):
        expenditure.dismiss(DismissType.UNAUTHORIZED_SUBMITTER)
    db.session.add(expenditure)
