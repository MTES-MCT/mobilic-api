from flask import g

from app import db
from app.domain.log_activities import log_activity, resolve_driver
from app.domain.log_vehicle_booking import log_vehicle_booking
from app.domain.team import enroll_or_release, get_or_create_team_mate
from app.helpers.errors import OverlappingMissionsError, add_non_blocking_error
from app.models import Mission


def begin_mission(
    user,
    event_time,
    first_activity_type,
    name=None,
    driver=None,
    vehicle_registration_number=None,
    vehicle_id=None,
    team=None,
):
    # 1. Check that user is not currently engaged in another mission
    user_current_mission = user.mission_at(event_time)
    if user_current_mission:
        raise OverlappingMissionsError(
            f"{user} is currently in a mission, and therefore cannot start a new one",
            user=user,
            conflicting_mission=user_current_mission,
        )

    # 2. Create the team mates if they don't exist
    fully_created_team = []
    if team:
        fully_created_team = [
            get_or_create_team_mate(user, team_mate_data)
            for team_mate_data in team
        ]
        db.session.flush()

    driver = resolve_driver(user, driver)

    # 3. Create the mission and log the activity
    mission = Mission(name=name, event_time=event_time, submitter=user)
    db.session.add(mission)
    db.session.flush()

    log_activity(
        submitter=user,
        user=user,
        mission=mission,
        type=first_activity_type,
        event_time=event_time,
        user_time=event_time,
        driver=driver,
    )

    # 4. Log vehicle booking
    log_vehicle_booking(
        vehicle_id=vehicle_id,
        registration_number=vehicle_registration_number,
        mission=mission,
        user_time=event_time,
        event_time=event_time,
        submitter=user,
    )

    # 5. Enroll team mates
    if fully_created_team:
        for team_mate in fully_created_team:
            try:
                enroll_or_release(
                    user, mission, team_mate, event_time, is_enrollment=True
                )
            except Exception as e:
                add_non_blocking_error(e)

    return mission
