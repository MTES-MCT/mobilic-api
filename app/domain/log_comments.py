from app import db
from app.domain.log_events import check_whether_event_should_be_logged
from app.domain.permissions import can_submitter_log_on_mission
from app.helpers.errors import AuthorizationError
from app.models import Comment


def log_comment(submitter, mission, event_time, content):
    if not can_submitter_log_on_mission(submitter, mission):
        raise AuthorizationError(
            f"The user is not authorized to log for this mission"
        )

    check_whether_event_should_be_logged(
        submitter_id=submitter.id,
        event_time=event_time,
        mission_id=mission.id,
        content=content,
        event_history=submitter.submitted_comments,
    )

    comment = Comment(
        event_time=event_time,
        content=content,
        submitter=submitter,
        mission=mission,
    )
    db.session.add(comment)

    return comment
