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

SUPER_ADMIN_EMAIL = "super.admin@test.com"
TEAM_ADMIN_EMAIL = "team.admin@test.com"

EMPLOYEE = "noteam.employee@test.com"
TEAM_EMPLOYEE = "team.employee@test.com"


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

    vehicle = Vehicle(
        registration_number=f"XXX-001-ABC",
        alias=f"Vehicule 1",
        submitter=super_admin,
        company_id=company.id,
    )
    db.session.add(vehicle)

    team_vehicle = Vehicle(
        registration_number=f"XXX-002-ABC",
        alias=f"Vehicule Team 1",
        submitter=super_admin,
        company_id=company.id,
    )
    db.session.add(team_vehicle)

    company_address = CompanyKnownAddress(
        alias=f"Entrepot 1",
        address=Address.get_or_create(
            geo_api_data=None, manual_address="1, rue de Paris"
        ),
        company_id=company.id,
    )
    db.session.add(company_address)

    team_address = CompanyKnownAddress(
        alias=f"Entrepot Team 1",
        address=Address.get_or_create(
            geo_api_data=None, manual_address="1, rue de Rennes"
        ),
        company_id=company.id,
    )
    db.session.add(team_address)

    team = Team(
        name="My team",
        company_id=company.id,
        admin_users=[team_admin],
        vehicles=[team_vehicle],
        known_addresses=[team_address],
    )

    no_team_employee = UserFactory.create(
        first_name=f"NoTeam", last_name=f"Employee", email=EMPLOYEE
    )
    EmploymentFactory.create(
        company=company,
        submitter=super_admin,
        user=no_team_employee,
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

    db.session.commit()
