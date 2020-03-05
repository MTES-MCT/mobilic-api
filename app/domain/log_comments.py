from app import db
from app.domain.log_events import get_response_if_event_should_not_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.models import Comment
from app.models.event import EventBaseContext


def log_group_comment(submitter, users, content, event_time):
    for user in users:
        log_comment(
            event_time=event_time,
            user=user,
            submitter=submitter,
            content=content,
        )


def log_comment(submitter, user, event_time, content):
    response_if_event_should_not_be_logged = get_response_if_event_should_not_be_logged(
        user=user,
        submitter=submitter,
        event_time=event_time,
        content=content,
        event_history=user.comments,
    )
    if response_if_event_should_not_be_logged:
        return

    comment = Comment(
        event_time=event_time,
        user=user,
        company_id=submitter.company_id,
        content=content,
        submitter=submitter,
        context=None
        if can_submitter_log_for_user(submitter, user)
        else EventBaseContext.UNAUTHORIZED_SUBMITTER,
    )
    db.session.add(comment)
