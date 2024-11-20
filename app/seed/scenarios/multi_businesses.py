from faker import Faker

from app import db
from app.models import Business
from app.models.business import BusinessType
from app.models.employment import Employment
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
)

fake = Faker("fr_FR")

ADMIN_EMAIL = "admin@multibusiness.com"
EMPLOYEE_EMAIL = "employee@multibusiness.com"


def run_scenario_multi_businesses():
    business_trm_long = Business.query.filter(
        Business.business_type == BusinessType.LONG_DISTANCE
    ).one_or_none()
    business_trm_short = Business.query.filter(
        Business.business_type == BusinessType.SHORT_DISTANCE
    ).one_or_none()
    business_trv = Business.query.filter(
        Business.business_type == BusinessType.VTC
    ).one_or_none()

    company_trm = CompanyFactory.create(
        usual_name="Entreprise TRM",
        siren=f"000009591",
        business=business_trm_long,
    )
    company_trv = CompanyFactory.create(
        usual_name="Entreprise TRV", siren=f"000009591", business=business_trv
    )

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Le",
        last_name="Gestionnaire",
    )
    employee = UserFactory.create(
        email=EMPLOYEE_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Agathe",
        last_name=f"Poulain",
    )
    for company in [company_trm, company_trv]:
        EmploymentFactory.create(
            company=company,
            submitter=admin,
            user=admin,
            has_admin_rights=True,
            business=company.business,
        )
        EmploymentFactory.create(
            company=company,
            submitter=admin,
            user=employee,
            has_admin_rights=False,
            business=company.business,
        )
        vehicle = Vehicle(
            registration_number=fake.license_plate(),
            alias=fake.word(),
            submitter=admin,
            company_id=company.id,
        )
        db.session.add(vehicle)

    db.session.commit()

    log_and_validate_mission(
        mission_name="Mission TRM",
        work_periods=[
            [
                get_time(how_many_days_ago=4, hour=5),
                get_time(how_many_days_ago=4, hour=21),
            ]
        ],
        company=company_trm,
        employee=employee,
    )

    log_and_validate_mission(
        mission_name="Mission TRV",
        work_periods=[
            [
                get_time(how_many_days_ago=2, hour=5),
                get_time(how_many_days_ago=2, hour=21),
            ]
        ],
        company=company_trv,
        employee=employee,
    )

    employment = Employment.query.filter(
        Employment.user_id == employee.id
    ).first()
    employment.business = business_trm_short
    db.session.commit()
