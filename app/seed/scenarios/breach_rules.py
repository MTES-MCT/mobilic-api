from app import db
from app.models import (
    Vehicle,
)
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
)
from app.seed.helpers import (
    get_time,
    log_and_validate_mission,
    DEFAULT_PASSWORD,
)

ADMIN_EMAIL = "breach.boss@test.com"
EMPLOYEE_EMAIL = "breach@test.com"


def run_scenario_breach_rules():
    company = CompanyFactory.create(
        usual_name=f"Rules Breaching Ltd", siren=f"00000404"
    )

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
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
        password=DEFAULT_PASSWORD,
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
        log_and_validate_mission(
            mission_name=f"Mission Before {i}",
            work_periods=[
                [
                    get_time(how_many_days_ago=10 + i, hour=8),
                    get_time(how_many_days_ago=10 + i, hour=10),
                ],
                [
                    get_time(how_many_days_ago=10 + i, hour=12),
                    get_time(how_many_days_ago=10 + i, hour=14),
                ],
            ],
            vehicle=vehicle,
            company=company,
            employee=employee,
        )

    ## MISSION Duree maximale du travail de jour
    log_and_validate_mission(
        mission_name="Mission Duree maximale du travail de jour - NATINF 11292",
        work_periods=[
            [
                get_time(how_many_days_ago=9, hour=6),
                get_time(how_many_days_ago=9, hour=10),
            ],
            [
                get_time(how_many_days_ago=9, hour=11),
                get_time(how_many_days_ago=9, hour=16),
            ],
            [
                get_time(how_many_days_ago=9, hour=16, minute=30),
                get_time(how_many_days_ago=9, hour=20, minute=30),
            ],
        ],
        vehicle=vehicle,
        company=company,
        employee=employee,
    )

    ## MISSION 1
    log_and_validate_mission(
        mission_name="Mission Pas assez de pause sur 24h - NATINF 20525",
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
    ## MISSION PAS DE PAUSE
    log_and_validate_mission(
        mission_name="Mission Pas de pause - Sanction Du Code Du Travail",
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
    log_and_validate_mission(
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
    log_and_validate_mission(
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
    log_and_validate_mission(
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
    log_and_validate_mission(
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
    log_and_validate_mission(
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
    ## MISSION Duree maximale du travail de jour
    log_and_validate_mission(
        mission_name="Mission Duree maximale du travail de nuit NATINF 32083",
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
