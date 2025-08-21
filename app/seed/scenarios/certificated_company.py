import datetime
from datetime import date

from app import db
from app.helpers.time import previous_month_period
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

NO_CERTIF_COMPANY_NAME = "Pas de certif Corp"
BRONZE_COMPANY_NAME = "Bronze Corp"
SILVER_COMPANY_NAME = "Argent Corp"
GOLD_COMPANY_NAME = "Or Corp"
DIAMOND_COMPANY_NAME = "Diamant Corp"


def run_scenario_certificated():

    month_start, _ = previous_month_period(date.today())

    company = CompanyFactory.create(
        usual_name="Les bons eleves", siren="00000822"
    )

    company_no_certif = CompanyFactory.create(
        usual_name=NO_CERTIF_COMPANY_NAME,
        siren="000011111",
        accept_certification_communication=True,
    )
    company_bronze = CompanyFactory.create(
        usual_name=BRONZE_COMPANY_NAME,
        siren="000011112",
        accept_certification_communication=True,
    )
    company_silver = CompanyFactory.create(
        usual_name=SILVER_COMPANY_NAME,
        siren="000011113",
        accept_certification_communication=True,
    )
    company_gold = CompanyFactory.create(
        usual_name=GOLD_COMPANY_NAME,
        siren="000011114",
        accept_certification_communication=True,
    )
    company_diamond = CompanyFactory.create(
        usual_name=DIAMOND_COMPANY_NAME,
        siren="000011115",
        accept_certification_communication=True,
    )

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Admin",
        last_name="Modele",
    )

    employee = UserFactory.create(
        email=EMPLOYEE_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Employee",
        last_name="Du Mois",
    )

    for c in [
        company,
        company_bronze,
        company_silver,
        company_gold,
        company_diamond,
        company_no_certif,
    ]:
        EmploymentFactory.create(
            company=c, submitter=admin, user=admin, has_admin_rights=True
        )
        EmploymentFactory.create(
            company=c,
            submitter=admin,
            user=employee,
            has_admin_rights=False,
        )

    vehicle = Vehicle(
        registration_number="XXX-001-BREACH",
        alias="Vehicule - Corp Breach",
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
            admin_validating=admin,
        )

    # log time in all companies to "have activity"
    hour = 5
    for c in [
        company_bronze,
        company_silver,
        company_gold,
        company_diamond,
        company_no_certif,
    ]:
        log_and_validate_mission(
            mission_name="Mission courte",
            work_periods=[
                [
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=5),
                        datetime.time(hour, 0),
                    ),
                    datetime.datetime.combine(
                        month_start + datetime.timedelta(days=5),
                        datetime.time(hour + 1, 0),
                    ),
                ],
            ],
            company=c,
            employee=employee,
            admin_validating=admin,
        )
        hour = hour + 2
