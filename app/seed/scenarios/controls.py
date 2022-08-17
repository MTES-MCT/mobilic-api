import datetime
from app.models.controller_control import ControllerControl
from app.seed import (
    CompanyFactory,
    ControllerFactory,
    UserFactory,
    EmploymentFactory,
)


def run_scenario_controls():
    company = CompanyFactory.create(
        usual_name="Controlled Corp", siren="77464376"
    )
    admin = UserFactory.create(
        password="password",
    )
    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )
    employee = UserFactory.create()
    EmploymentFactory.create(
        company=company,
        submitter=admin,
        user=employee,
        has_admin_rights=False,
    )

    controller_user = ControllerFactory.create(email="controller@test.com")

    ControllerControl.get_or_create_mobilic_control(
        controller_id=controller_user.id,
        user_id=employee.id,
        qr_code_generation_time=datetime.datetime.now(),
    )
