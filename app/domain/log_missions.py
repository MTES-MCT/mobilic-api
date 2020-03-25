from app import db
from app.domain.log_events import check_whether_event_should_not_be_logged
from app.models import Mission


def log_mission(name, user_time, event_time, submitter):
    if check_whether_event_should_not_be_logged(
        submitter=submitter,
        event_time=event_time,
        name=name,
        event_history=submitter.submitted_missions,
    ):
        return

    db.session.add(
        Mission(
            name=name,
            user_time=user_time,
            event_time=event_time,
            submitter=submitter,
            company_id=submitter.company_id,
        )
    )
