from app import db
from app.domain.validation import validate_mission
from app.models.address import Address
from app.models.company_known_address import CompanyKnownAddress
from app.models.team import Team
from app.models.vehicle import Vehicle
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
)
from app.seed.helpers import (
    get_time,
    log_and_validate_mission,
    DEFAULT_PASSWORD,
    AuthenticatedUserContext,
)

SUPER_ADMIN_EMAIL = "super.admin.teams@test.com"


def create_vehicle(id, alias, company):
    vehicle = Vehicle(
        registration_number=f"XXX-00{id}-ABC",
        alias=alias,
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
        password=DEFAULT_PASSWORD,
        first_name="Super",
        last_name="Admin",
    )
    EmploymentFactory.create(
        company=company,
        submitter=super_admin,
        user=super_admin,
        has_admin_rights=True,
    )

    vehicles = [
        create_vehicle(i, f"Vehicule Team {i}", company) for i in range(1, 5)
    ]
    vehicles += [create_vehicle(5, "Vehicule No Team", company)]
    addresses = [
        create_address(f"Entrepot Team {i}", f"{i}, rue de Rennes", company)
        for i in range(1, 5)
    ]
    addresses += [
        create_address("Entrepot No Team", "1, rue de Paris", company)
    ]

    admins = [
        UserFactory.create(
            email=f"team.admin{i}@test.com",
            password=DEFAULT_PASSWORD,
            first_name="Team",
            last_name=f"Admin {i}",
        )
        for i in range(1, 5)
    ]
    for idx_admin, admin in enumerate(admins):
        EmploymentFactory.create(
            company=company,
            submitter=super_admin,
            user=admins[idx_admin],
            has_admin_rights=True,
        )

    teams = [
        Team(
            name=f"Team {i}",
            company_id=company.id,
            admin_users=admins[:i],
            vehicles=[vehicles[i - 1]],
            known_addresses=[addresses[i - 1]],
        )
        for i in range(1, 5)
    ]

    employees = [
        UserFactory.create(
            email=f"team.employee{i}@test.com",
            password=DEFAULT_PASSWORD,
            first_name="Employee",
            last_name=f"Numero {i}",
        )
        for i in range(1, 6)
    ]

    for idx_e in range(0, 4):
        e = employees[idx_e]
        EmploymentFactory.create(
            company=company,
            submitter=super_admin,
            user=e,
            has_admin_rights=False,
            team=teams[idx_e],
        )

    EmploymentFactory.create(
        company=company,
        submitter=super_admin,
        user=employees[-1],
        has_admin_rights=False,
    )

    db.session.commit()

    # log missions with alerts on past few months
    for i, days_ago in enumerate(range(0, 200, 20)):
        mission_validated = [
            log_and_validate_mission(
                mission_name=f"Mission Validée {idx_e}",
                work_periods=[
                    [
                        get_time(how_many_days_ago=days_ago, hour=6),
                        get_time(how_many_days_ago=days_ago, hour=10),
                    ],
                    [
                        get_time(
                            how_many_days_ago=days_ago,
                            hour=10 if i % 2 == 0 else 11,
                            minute=13,
                        ),
                        get_time(how_many_days_ago=days_ago, hour=18),
                    ],
                ],
                vehicle=vehicles[idx_e - 1],
                company=company,
                employee=e,
                validate=True,
            )
            for idx_e, e in enumerate(employees)
        ]
        for idx_m, m in enumerate(mission_validated):
            employee = employees[idx_m]
            with AuthenticatedUserContext(user=super_admin):
                validate_mission(
                    mission=m, submitter=super_admin, for_user=employee
                )

    db.session.commit()
