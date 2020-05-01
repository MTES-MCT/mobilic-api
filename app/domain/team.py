from app import db, app
from app.domain.log_activities import log_activity
from app.helpers.authentication import AuthorizationError
from app.models import User
from app.models.activity import ActivityType


def get_or_create_team_mate(submitter, team_mate_data):
    team_mate_id = team_mate_data.get("id")
    if not team_mate_id:
        user = User(
            first_name=team_mate_data.get("first_name"),
            last_name=team_mate_data.get("last_name"),
            company_id=submitter.company_id,
        )
        db.session.add(user)
        return user
    else:
        return User.query.get(team_mate_id)


def enroll_or_release(submitter, team_mate, event_time, is_enrollment):
    mission = submitter.mission_at(event_time)

    app.logger.info(f"Enrolling {team_mate} on {mission}")

    if not mission:
        raise ValueError(
            f"{submitter} cannot enroll {team_mate} at {event_time} because the former is not engaged in a mission at that time"
        )

    driver = None
    if is_enrollment:
        submitter_activity = submitter.latest_acknowledged_activity_at(
            event_time
        )
        type = submitter_activity.type
        driver = submitter_activity.driver
    else:
        type = ActivityType.REST

    log_activity(
        submitter=submitter,
        user=team_mate,
        mission=mission,
        type=type,
        event_time=event_time,
        user_time=event_time,
        driver=driver,
    )
