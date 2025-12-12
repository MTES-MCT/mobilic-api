import random

from app import db
from app.models import Business
from app.models.expenditure import ExpenditureType
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
)
from app.seed.helpers import (
    add_employee,
    get_time,
    DEFAULT_PASSWORD,
    create_vehicle,
    create_address,
    log_and_validate_mission,
)

ADMIN_EMAIL = "test.charge@admin.com"
NB_EMPLOYEES = 2
NB_HISTORY_DELETED = 4
# most recent day: nobody validates
# day before: only employee validates
# before: two validations
NB_HISTORY_REGULAR = 5
NB_VEHICLES = 20
NB_ADDRESSES = 20
MINIMUM_HOUR = 3
MAXIMUM_HOUR = 18


def _get_random_work_periods(days_ago):
    work_periods = []
    nb_activities = random.choice([1, 2])
    hours = random.sample(
        range(MINIMUM_HOUR, MAXIMUM_HOUR + 1), nb_activities * 2
    )
    hours.sort()
    for i in range(nb_activities):
        work_periods.append(
            [
                get_time(how_many_days_ago=days_ago, hour=hours[i * 2]),
                get_time(how_many_days_ago=days_ago, hour=hours[i * 2 + 1]),
            ]
        )
    return work_periods


def run_scenario_lot_of_missions():
    business = Business.query.first()
    company = CompanyFactory.create(
        usual_name=f"Test Charge",
        siren=f"1000001",
        number_workers=NB_EMPLOYEES + 1,
        business=business,
    )
    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Prenom",
        last_name="Nom",
    )
    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )
    [create_vehicle(company=company) for _ in range(NB_VEHICLES)]
    [create_address(company=company) for _ in range(NB_ADDRESSES)]
    employees = [
        add_employee(
            company=company,
            admin=admin,
        )
        for _ in range(NB_EMPLOYEES)
    ]
    db.session.commit()

    deleted_missions = []
    for employee in employees:

        for nb_days_ago in range(NB_HISTORY_DELETED):
            mission = log_and_validate_mission(
                f"Mission supprimée {nb_days_ago + 1}",
                company=company,
                employee=employee,
                vehicle=random.choice(company.vehicles),
                address=random.choice(company.known_addresses),
                add_location_entry=True,
                work_periods=_get_random_work_periods(
                    days_ago=nb_days_ago + 1
                ),
                employee_comment="Commentaire du salarié",
                employee_expenditure=random.choice(list(ExpenditureType)),
            )

            deleted_missions.append(mission)

    db.session.commit()
    from app.tests.helpers import make_authenticated_request, ApiRequests

    # Admin cancels missions
    for deleted_mission in deleted_missions:
        make_authenticated_request(
            time=get_time(how_many_days_ago=1, hour=MAXIMUM_HOUR + 2),
            submitter_id=admin.id,
            query=ApiRequests.cancel_mission,
            variables=dict(
                mission_id=deleted_mission.id,
                user_id=deleted_mission.submitter_id,
            ),
        )
    db.session.commit()

    # Regular missions
    for employee in employees:
        for nb_days_ago in range(NB_HISTORY_REGULAR):
            employee_validates = nb_days_ago > 0
            admin_validates = nb_days_ago > 1
            log_and_validate_mission(
                mission_name=f"Mission {nb_days_ago}",
                company=company,
                employee=employee,
                vehicle=random.choice(company.vehicles),
                address=random.choice(company.known_addresses),
                add_location_entry=True,
                work_periods=_get_random_work_periods(
                    days_ago=nb_days_ago + 1
                ),
                employee_expenditure=random.choice(list(ExpenditureType)),
                validate=employee_validates,
                admin_validating=admin if admin_validates else None,
                employee_comment="Commentaire du salarié",
            )
            db.session.commit()
