from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import User
from app.models.activity import ActivityType
from app.seed import AuthenticatedUserContext
from app.seed.helpers import get_time, create_mission
from app.seed.scenarios.formations import _clean_recent_data


def run_scenario_formation_admin(employee_email):
    """
    Adds three missions in the history of the user.
    For one mission, the user modifies its input before validating.
    The history should produce regulatory alerts
    :param employee_email: email of the target user
    """

    employee = User.query.filter(User.email == employee_email).one_or_none()
    if not employee:
        return

    _clean_recent_data(employee)

    company = employee.employments[0].company

    missions_to_create = [
        {
            "name": "Mission validée 1",
            "hours": [
                [
                    get_time(how_many_days_ago=4, hour=10),
                    get_time(how_many_days_ago=4, hour=13),
                ],
                [
                    get_time(how_many_days_ago=4, hour=14),
                    get_time(how_many_days_ago=4, hour=21),
                ],
            ],
            "validate": True,
        },
        {
            "name": "Mission validée 2",
            "hours": [
                [
                    get_time(how_many_days_ago=3, hour=9, minute=30),
                    get_time(how_many_days_ago=3, hour=11, minute=59),
                ],
                [
                    get_time(how_many_days_ago=3, hour=12, minute=10),
                    get_time(how_many_days_ago=3, hour=17),
                ],
            ],
            "validate": True,
        },
        {
            "name": "Mission modifiée",
            "hours": [
                [
                    get_time(how_many_days_ago=2, hour=8, minute=12),
                    get_time(how_many_days_ago=2, hour=11, minute=47),
                ],
                [
                    get_time(how_many_days_ago=2, hour=12, minute=25),
                    get_time(how_many_days_ago=2, hour=14, minute=42),
                ],
            ],
            "validate": False,
        },
    ]
    missions = []
    for mission_to_create in missions_to_create:
        name = mission_to_create.get("name")
        mission = create_mission(
            name=name,
            company=company,
            time=mission_to_create.get("hours")[0][0],
            submitter=employee,
        )
        db.session.commit()

        with AuthenticatedUserContext(user=employee):
            hours = mission_to_create.get("hours")
            for hour in hours:
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=mission,
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=hour[1],
                    start_time=hour[0],
                    end_time=hour[1],
                )
            db.session.commit()
            if mission_to_create.get("validate"):
                validate_mission(
                    submitter=employee,
                    mission=mission,
                    for_user=employee,
                )
        missions.append(mission)
        db.session.commit()

    last_mission = missions[-1]
    with AuthenticatedUserContext(user=employee):
        from app.tests.helpers import make_authenticated_request, ApiRequests

        make_authenticated_request(
            time=get_time(how_many_days_ago=2, hour=20),
            submitter_id=employee.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activity_id=last_mission.activities[0].id,
                start_time=get_time(how_many_days_ago=2, hour=9, minute=55),
            ),
        )
        make_authenticated_request(
            time=get_time(how_many_days_ago=2, hour=20),
            submitter_id=employee.id,
            query=ApiRequests.validate_mission,
            variables=dict(
                mission_id=last_mission.id, users_ids=[employee.id]
            ),
        )
    db.session.commit()
