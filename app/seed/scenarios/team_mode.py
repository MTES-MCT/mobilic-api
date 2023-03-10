from app import db
from app.models.address import Address
from app.models.company_known_address import CompanyKnownAddress
from app.models.team import Team
from app.models.vehicle import Vehicle
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
)
from app.seed.helpers import get_time, log_and_validate_mission

SUPER_ADMIN_EMAIL = "super.admin@test.com"
TEAM_ADMIN_EMAIL = "team.admin@test.com"

TEAM_EMPLOYEE = "team.employee@test.com"


def create_vehicle(id, alias, admin, company):
    vehicle = Vehicle(
        registration_number=f"XXX-00{id}-ABC",
        alias=alias,
        submitter=admin,
        company_id=company.id,
    )
    db.session.add(vehicle)
    return vehicle


def create_address(alias, address, company):
    company_address = CompanyKnownAddress(
        alias=alias,
        address=Address.get_or_create(
            geo_api_data=None, manual_address=address
        ),
        company_id=company.id,
    )
    db.session.add(company_address)
    return company_address


def run_scenario_team_mode():
    company = CompanyFactory.create(
        usual_name=f"Team Mode Ltd", siren=f"00000959"
    )

    super_admin = UserFactory.create(
        email=SUPER_ADMIN_EMAIL,
        password="password123!",
        first_name="Super",
        last_name="Admin",
    )
    EmploymentFactory.create(
        company=company,
        submitter=super_admin,
        user=super_admin,
        has_admin_rights=True,
    )

    team_admin = UserFactory.create(
        email=TEAM_ADMIN_EMAIL,
        password="password123!",
        first_name="Team",
        last_name="Admin",
    )
    EmploymentFactory.create(
        company=company,
        submitter=super_admin,
        user=team_admin,
        has_admin_rights=True,
    )

    team_vehicle = create_vehicle(1, "Vehicule Team 1", super_admin, company)
    for i in range(2, 5):
        no_team_vehicle = create_vehicle(
            i, f"Vehicule {i}", super_admin, company
        )

    team_address = create_address(
        "Entrepot Team 1", "1, rue de Rennes", company
    )
    for i in range(2, 5):
        create_address(f"Entrepot {i}", f"{i}, rue de Paris", company)

    team = Team(
        name="My team",
        company_id=company.id,
        admin_users=[team_admin],
        vehicles=[team_vehicle],
        known_addresses=[team_address],
    )

    no_team_employees = [
        UserFactory.create(
            first_name=f"NoTeam",
            last_name=f"Employee {i}",
            email=f"noteam.employee{i}@test.com",
        )
        for i in range(5)
    ]
    for e in no_team_employees:
        EmploymentFactory.create(
            company=company,
            submitter=super_admin,
            user=e,
            has_admin_rights=False,
        )

    team_employee = UserFactory.create(
        first_name=f"Team", last_name=f"Employee", email=TEAM_EMPLOYEE
    )
    EmploymentFactory.create(
        company=company,
        submitter=super_admin,
        user=team_employee,
        has_admin_rights=False,
        team=team,
    )

    for idx_e, nte in enumerate(no_team_employees):
        log_and_validate_mission(
            mission_name=f"Mission pas equipe {idx_e}",
            work_periods=[
                [
                    get_time(how_many_days_ago=2, hour=6),
                    get_time(how_many_days_ago=2, hour=10),
                ]
            ],
            vehicle=no_team_vehicle,
            company=company,
            employee=nte,
        )

    log_and_validate_mission(
        mission_name="Mission equipe",
        work_periods=[
            [
                get_time(how_many_days_ago=2, hour=5),
                get_time(how_many_days_ago=2, hour=11),
            ]
        ],
        vehicle=team_vehicle,
        company=company,
        employee=team_employee,
    )

    db.session.commit()
