from app import db
from app.domain.log_activities import (
    log_activity,
    check_and_fix_inconsistencies_created_by_new_activity,
)
from app.domain.log_events import check_whether_event_should_not_be_logged
from app.models import User, TeamEnrollment
from app.models.activity import ActivityType
from app.models.team_enrollment import TeamEnrollmentType


def enroll(submitter, user_id, first_name, last_name, user_time, event_time):
    if not user_id:
        user = User(
            first_name=first_name,
            last_name=last_name,
            company_id=submitter.company_id,
        )
        db.session.add(user)
    else:
        user = User.query.get(user_id)

    if check_whether_event_should_not_be_logged(
        user=user,
        submitter=submitter,
        event_time=event_time,
        event_history=submitter.submitted_team_enrollments,
        user_time=user_time,
    ):
        return

    # 1. Create enrollment
    team_enrollment = TeamEnrollment(
        type=TeamEnrollmentType.ENROLL,
        user_time=user_time,
        event_time=event_time,
        user=user,
        submitter=submitter,
    )
    db.session.add(team_enrollment)

    # 2. Create activity if needed
    team_activity_at_enrollment_time = submitter.latest_acknowledged_activity_at(
        user_time
    )
    if (
        team_activity_at_enrollment_time
        and team_activity_at_enrollment_time.type != ActivityType.REST
    ):
        activity = log_activity(
            submitter=submitter,
            user=user,
            type=team_activity_at_enrollment_time.type,
            event_time=event_time,
            user_time=user_time,
            driver=team_activity_at_enrollment_time.driver,
        )
        check_and_fix_inconsistencies_created_by_new_activity(
            activity, event_time
        )


def unenroll(submitter, user_id, user_time, event_time):
    user = User.query.get(user_id)

    if check_whether_event_should_not_be_logged(
        user=user,
        submitter=submitter,
        event_time=event_time,
        event_history=submitter.submitted_team_enrollments,
        user_time=user_time,
    ):
        return

    team_enrollment = TeamEnrollment(
        type=TeamEnrollmentType.REMOVE,
        user_time=user_time,
        event_time=event_time,
        user=user,
        submitter=submitter,
    )
    db.session.add(team_enrollment)

    log_activity(
        submitter=submitter,
        user=user,
        type=ActivityType.REST,
        event_time=event_time,
        user_time=user_time,
        driver=None,
    )
