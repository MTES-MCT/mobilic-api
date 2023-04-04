import datetime
from datetime import date

from app import db
from app.domain.certificate_criteria import previous_month_period
from app.models import (
    Vehicle,
)
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
)
from app.seed.helpers import (
    log_and_validate_mission,
    DEFAULT_PASSWORD,
)

ADMIN_EMAIL = "certificated@admin.com"
EMPLOYEE_EMAIL = "certificated@employee.com"


def run_scenario_certificated():

    month_start, _ = previous_month_period(date.today())

    company = CompanyFactory.create(
        usual_name="Les bons eleves", siren="00000822"
    )

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Admin",
        last_name="Modele",
    )

    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )

    employee = UserFactory.create(
        email=EMPLOYEE_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Employee",
        last_name="Du Mois",
    )
    EmploymentFactory.create(
        company=company,
        submitter=admin,
        user=employee,
        has_admin_rights=False,
    )

    vehicle = Vehicle(
        registration_number="XXX-001-BREACH",
        alias=f"Vehicule - Corp Breach",
        submitter=admin,
        company_id=company.id,
    )
    db.session.add(vehicle)

    # Needs 10 days with 2 activities
    # No rules breached
    # validated by admin < 7 days
    # real time
    # no changes

    for i in range(5):
        log_and_validate_mission(
            mission_name=f"Mission Week 1 Day {i}",
            work_periods=[
                [
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i),
                        datetime.time(8, 0),
                    ),
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i),
                        datetime.time(10, 0),
                    ),
                ],
                [
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i),
                        datetime.time(12, 0),
                    ),
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i),
                        datetime.time(14, 0),
                    ),
                ],
            ],
            company=company,
            employee=employee,
            vehicle=vehicle,
            admin_validating=admin,
        )

        log_and_validate_mission(
            mission_name=f"Mission Week 2 Day {i}",
            work_periods=[
                [
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i + 7),
                        datetime.time(8),
                    ),
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i + 7),
                        datetime.time(10),
                    ),
                ],
                [
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i + 7),
                        datetime.time(12),
                    ),
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i + 7),
                        datetime.time(14),
                    ),
                ],
            ],
            company=company,
            employee=employee,
            vehicle=vehicle,
            admin_validating=admin,
        )

        log_and_validate_mission(
            mission_name=f"Mission Week 3 Day {i}",
            work_periods=[
                [
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i + 14),
                        datetime.time(8),
                    ),
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i + 14),
                        datetime.time(10),
                    ),
                ],
                [
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i + 14),
                        datetime.time(12),
                    ),
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=i + 14),
                        datetime.time(14),
                    ),
                ],
            ],
            company=company,
            employee=employee,
            vehicle=vehicle,
            admin_validating=admin,
        )
