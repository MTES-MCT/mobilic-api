from app import db
from app.domain.log_events import check_whether_event_should_be_logged
from app.domain.permissions import can_submitter_log_for_user
from app.helpers.authentication import AuthorizationError
from app.models import Comment


def log_group_comment(submitter, content, event_time):
    for user in submitter.mission_at(event_time).team_at(event_time):
        log_comment(
            event_time=event_time,
            user=user,
            submitter=submitter,
            content=content,
        )


def log_comment(submitter, user, event_time, content):
    check_whether_event_should_be_logged(
        user=user,
        submitter=submitter,
        event_time=event_time,
        content=content,
        event_history=user.comments,
    )

    comment = Comment(
        event_time=event_time, user=user, content=content, submitter=submitter,
    )
    if not can_submitter_log_for_user(submitter, user):
        raise AuthorizationError(f"Event is submitted from unauthorized user")
    db.session.add(comment)
