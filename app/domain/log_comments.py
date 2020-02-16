from app import db
from app.domain.log_events import get_response_if_event_should_not_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.models import Comment
from app.models.event import EventBaseValidationStatus


def log_group_comment(
    submitter, company, users, content, event_time, reception_time
):
    for user in users:
        log_comment(
            event_time=event_time,
            reception_time=reception_time,
            user=user,
            company=company,
            submitter=submitter,
            content=content,
        )


def log_comment(submitter, user, company, event_time, reception_time, content):
    response_if_event_should_not_be_logged = get_response_if_event_should_not_be_logged(
        user=user,
        submitter=submitter,
        company=company,
        event_time=event_time,
        reception_time=reception_time,
        content=content,
        event_history=user.comments,
    )
    if response_if_event_should_not_be_logged:
        return

    comment = Comment(
        event_time=event_time,
        reception_time=reception_time,
        user=user,
        company=company,
        content=content,
        submitter=submitter,
        validation_status=EventBaseValidationStatus.PENDING
        if can_submitter_log_for_user(submitter, user, company)
        else EventBaseValidationStatus.UNAUTHORIZED_SUBMITTER,
    )
    db.session.add(comment)
