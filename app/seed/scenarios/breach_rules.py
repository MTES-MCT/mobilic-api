from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import (
    MissionEnd,
    Mission,
    Vehicle,
)
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    AuthenticatedUserContext,
)
from app.seed.helpers import get_time

ADMIN_EMAIL = "breach.boss@test.com"
EMPLOYEE_EMAIL = "breach@test.com"


def create_mission(name, company, time, submitter, vehicle):
    mission = Mission(
        name=name,
        company=company,
        reception_time=time,
        submitter=submitter,
        vehicle=vehicle,
    )
    db.session.add(mission)
    return mission


def log_mission(mission_name, work_periods, company, employee, vehicle):
    mission = create_mission(
        name=mission_name,
        company=company,
        time=work_periods[0][0],
        submitter=employee,
        vehicle=vehicle,
    )
    db.session.commit()

    with AuthenticatedUserContext(user=employee):
        for wp in work_periods:
            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=wp[1],
                start_time=wp[0],
                end_time=wp[1],
            )
        db.session.add(
            MissionEnd(
                submitter=employee,
                reception_time=work_periods[-1][1],
                user=employee,
                mission=mission,
            )
        )
        validate_mission(
            submitter=employee,
            mission=mission,
            for_user=employee,
        )


def run_scenario_breach_rules():
    company = CompanyFactory.create(
        usual_name=f"Rules Breaching Ltd", siren=f"00000404"
    )

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password="password",
        first_name="Breach",
        last_name="Boss",
    )

    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )

    vehicle = Vehicle(
        registration_number=f"XXX-001-BREACH",
        alias=f"Vehicule - Corp Breach",
        submitter=admin,
        company_id=company.id,
    )
    db.session.add(vehicle)

    employee = UserFactory.create(
        email=EMPLOYEE_EMAIL,
        password="password",
        first_name=f"Raoul",
        last_name=f"Breacher",
    )
    EmploymentFactory.create(
        company=company,
        submitter=admin,
        user=employee,
        has_admin_rights=False,
    )

    ## works 5 days before:
    for i in range(5):
        log_mission(
            mission_name=f"Mission Before {i}",
            work_periods=[
                [
                    get_time(how_many_days_ago=9 + i, hour=8),
                    get_time(how_many_days_ago=9 + i, hour=10),
                ],
                [
                    get_time(how_many_days_ago=9 + i, hour=12),
                    get_time(how_many_days_ago=9 + i, hour=14),
                ],
            ],
            vehicle=vehicle,
            company=company,
            employee=employee,
        )

    ## MISSION 1
    log_mission(
        mission_name="Mission 1",
        work_periods=[
            [
                get_time(how_many_days_ago=8, hour=8),
                get_time(how_many_days_ago=8, hour=10),
            ],
            [
                get_time(how_many_days_ago=8, hour=12),
                get_time(how_many_days_ago=8, hour=14),
            ],
        ],
        vehicle=vehicle,
        company=company,
        employee=employee,
    )
    ## MISSION 2
    log_mission(
        mission_name="Mission 2",
        work_periods=[
            [
                get_time(how_many_days_ago=7, hour=8),
                get_time(how_many_days_ago=7, hour=14, minute=5),
            ],
        ],
        vehicle=vehicle,
        company=company,
        employee=employee,
    )
    ## MISSION 3
    log_mission(
        mission_name="Mission 3",
        work_periods=[
            [
                get_time(how_many_days_ago=6, hour=4),
                get_time(how_many_days_ago=6, hour=8),
            ],
            [
                get_time(how_many_days_ago=6, hour=16),
                get_time(how_many_days_ago=6, hour=20),
            ],
        ],
        vehicle=vehicle,
        company=company,
        employee=employee,
    )
    ## MISSION 4
    log_mission(
        mission_name="Mission 4",
        work_periods=[
            [
                get_time(how_many_days_ago=6, hour=22),
                get_time(how_many_days_ago=5, hour=3, minute=55),
            ],
        ],
        vehicle=vehicle,
        company=company,
        employee=employee,
    )
    ## MISSION 5
    log_mission(
        mission_name="Mission 5",
        work_periods=[
            [
                get_time(how_many_days_ago=4, hour=4),
                get_time(how_many_days_ago=4, hour=8),
            ],
            [
                get_time(how_many_days_ago=4, hour=16),
                get_time(how_many_days_ago=4, hour=20),
            ],
        ],
        vehicle=vehicle,
        company=company,
        employee=employee,
    )
    ## MISSION 6
    log_mission(
        mission_name="Mission 6",
        work_periods=[
            [
                get_time(how_many_days_ago=4, hour=22),
                get_time(how_many_days_ago=3, hour=4),
            ],
        ],
        vehicle=vehicle,
        company=company,
        employee=employee,
    )
    ## MISSION 7
    log_mission(
        mission_name="Mission 7",
        work_periods=[
            [
                get_time(how_many_days_ago=2, hour=8),
                get_time(how_many_days_ago=2, hour=12),
            ],
            [
                get_time(how_many_days_ago=2, hour=12, minute=30),
                get_time(how_many_days_ago=2, hour=16, minute=30),
            ],
            [
                get_time(how_many_days_ago=2, hour=16, minute=45),
                get_time(how_many_days_ago=2, hour=19, minute=45),
            ],
        ],
        vehicle=vehicle,
        company=company,
        employee=employee,
    )
    ## MISSION 8
    log_mission(
        mission_name="Mission 8",
        work_periods=[
            [
                get_time(how_many_days_ago=1, hour=1),
                get_time(how_many_days_ago=1, hour=5),
            ],
            [
                get_time(how_many_days_ago=1, hour=8),
                get_time(how_many_days_ago=1, hour=15),
            ],
        ],
        vehicle=vehicle,
        company=company,
        employee=employee,
    )

    # with AuthenticatedUserContext(user=admin):
    #     validate_mission(
    #         submitter=admin,
    #         mission=history_mission,
    #         for_user=employee,
    #     )
    # db.session.commit()

    # db.session.commit()
