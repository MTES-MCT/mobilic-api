from app import db
from app.domain.log_activities import log_activity, resolve_driver
from app.domain.log_vehicle_booking import log_vehicle_booking
from app.domain.team import enroll
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
    if user.mission_at(event_time):
        raise ValueError(
            f"{user} is currently in a mission, and therefore cannot start a new one"
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

    # 4. Enroll team mates
    if team:
        for team_mate in team:
            enroll(user, team_mate, event_time)

    return mission
