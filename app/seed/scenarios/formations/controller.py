from future.backports.datetime import timedelta

from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import User, Employment
from app.models.activity import ActivityType
from app.seed.helpers import get_time, create_mission, AuthenticatedUserContext
from app.seed.scenarios.formations import _clean_recent_data


def run_scenario_formation_controller_2(employee_email):
    """
    Over two weeks, add 5 missions a week with alerts, but admin modifies the mission
    before validating not to have alerts (except on the last day of each week)
    :param employee_email: email of the target user
    """
    employee = User.query.filter(User.email == employee_email).one_or_none()
    if not employee:
        return

    _clean_recent_data(employee)

    company = employee.employments[0].company
    admin = (
        Employment.query.filter(
            Employment.has_admin_rights == True,
            Employment.company_id == company.id,
        )
        .first()
        .user
    )

    for week in range(2):
        for day in range(5):
            start = get_time(
                how_many_days_ago=2 + day + 7 * week, hour=7, minute=30
            )
            end = get_time(how_many_days_ago=2 + day + 7 * week, hour=19)
            mission = create_mission(
                name="mission",
                company=company,
                time=start,
                submitter=employee,
            )
            db.session.commit()
            with AuthenticatedUserContext(user=employee):
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=mission,
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=end,
                    start_time=start,
                    end_time=end,
                )
                db.session.commit()

            from app.tests.helpers import (
                make_authenticated_request,
                ApiRequests,
            )

            with AuthenticatedUserContext(user=employee):
                make_authenticated_request(
                    time=end + timedelta(minutes=20),
                    submitter_id=employee.id,
                    query=ApiRequests.validate_mission,
                    variables=dict(
                        mission_id=mission.id, users_ids=[employee.id]
                    ),
                )

            with AuthenticatedUserContext(user=admin):
                make_authenticated_request(
                    time=end + timedelta(minutes=40),
                    submitter_id=admin.id,
                    query=ApiRequests.validate_mission,
                    variables=dict(
                        mission_id=mission.id,
                        users_ids=[employee.id],
                        activity_items=(
                            [
                                {
                                    "edit": {
                                        "activityId": mission.activities[0].id,
                                        "startTime": start
                                        + timedelta(hours=2, minutes=30),
                                        "endTime": start
                                        + timedelta(hours=6, minutes=30),
                                    }
                                },
                                {
                                    "log": {
                                        "userId": employee.id,
                                        "startTime": start
                                        + timedelta(hours=7, minutes=30),
                                        "endTime": start
                                        + timedelta(hours=11, minutes=30),
                                        "type": "drive",
                                        "switch": False,
                                        "missionId": mission.id,
                                    }
                                },
                            ]
                            if day > 0
                            else []
                        ),
                    ),
                )


def run_scenario_formation_controller_1(employee_email):
    """
    Adds 4 x 2 missions on past two weeks with some regulatory alerts
    Adds daily missions for 14 days before that to trigger weekly alerts
    :param employee_email: email of the target user
    """
    employee = User.query.filter(User.email == employee_email).one_or_none()
    if not employee:
        return

    _clean_recent_data(employee)

    company = employee.employments[0].company
    admin = (
        Employment.query.filter(
            Employment.has_admin_rights == True,
            Employment.company_id == company.id,
        )
        .first()
        .user
    )

    missions_to_create = []
    for week in [0, 1]:
        missions_to_create += [
            {
                "name": "Mission 1",
                "hours": [
                    [
                        get_time(how_many_days_ago=1 + 7 * week, hour=10),
                        get_time(how_many_days_ago=1 + 7 * week, hour=13),
                    ],
                    [
                        get_time(how_many_days_ago=1 + 7 * week, hour=14),
                        get_time(
                            how_many_days_ago=1 + 7 * week, hour=23, minute=45
                        ),
                    ],
                ],
            },
            {
                "name": "Mission 2",
                "hours": [
                    [
                        get_time(how_many_days_ago=2 + 7 * week, hour=10),
                        get_time(how_many_days_ago=2 + 7 * week, hour=12),
                    ],
                    [
                        get_time(how_many_days_ago=2 + 7 * week, hour=13),
                        get_time(how_many_days_ago=2 + 7 * week, hour=16),
                    ],
                ],
            },
            {
                "name": "Mission 3",
                "hours": [
                    [
                        get_time(
                            how_many_days_ago=3 + 7 * week, hour=9, minute=32
                        ),
                        get_time(
                            how_many_days_ago=3 + 7 * week, hour=19, minute=51
                        ),
                    ],
                ],
            },
            {
                "name": "Mission 4",
                "hours": [
                    [
                        get_time(
                            how_many_days_ago=4 + 7 * week, hour=8, minute=27
                        ),
                        get_time(
                            how_many_days_ago=4 + 7 * week, hour=14, minute=52
                        ),
                    ],
                    [
                        get_time(
                            how_many_days_ago=4 + 7 * week, hour=15, minute=30
                        ),
                        get_time(how_many_days_ago=4 + 7 * week, hour=19),
                    ],
                ],
            },
        ]

    for i in range(14):
        missions_to_create.append(
            {
                "name": "Mission",
                "hours": [
                    [
                        get_time(how_many_days_ago=14 + i, hour=8),
                        get_time(how_many_days_ago=14 + i, hour=11, minute=30),
                    ],
                    [
                        get_time(how_many_days_ago=14 + i, hour=13),
                        get_time(how_many_days_ago=14 + i, hour=18, minute=30),
                    ],
                ],
            }
        )

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
            validate_mission(
                submitter=employee,
                mission=mission,
                for_user=employee,
            )

        with AuthenticatedUserContext(user=admin):
            validate_mission(
                submitter=admin,
                mission=mission,
                for_user=employee,
            )
        db.session.commit()
