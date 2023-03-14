from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
)
from app.seed.helpers import DEFAULT_PASSWORD

ADMIN_EMAIL = "invitations.admin@test.com"
EMPLOYEE_EMAIL = "invitations.employee@test.com"


def run_scenario_invitations():
    company = CompanyFactory.create(
        usual_name="Invitations Corp", siren="1122335"
    )

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Invitations",
        last_name="Admin",
    )
    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )

    UserFactory.create(
        email=EMPLOYEE_EMAIL,
        password=DEFAULT_PASSWORD,
    )
