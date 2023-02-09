from argon2 import PasswordHasher
from app import db
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
)
from app.seed.factories import (
    OAuth2ClientFactory,
    ThirdPartyApiKeyFactory,
    ThirdPartyClientCompanyFactory,
    ThirdPartyClientEmploymentFactory,
)
from datetime import datetime


ADMIN_EMAIL = "admin@3rdparty.com"
EMPLOYEE_NOT_INVITED_EMAIL = "empl-not-invited@3rdparty.com"
EMPLOYEE_INVITED_EMAIL = "empl-invited@3rdparty.com"
EMPLOYEE_CONFIRMED_EMAIL = "empl-confirmed@3rdparty.com"
EMPLOYEE_DISMISSED_EMAIL = "empl-dismissed@3rdparty.com"
API_KEY = "012345678901234567890123456789012345678901234567890123456789"


def run_scenario_third_party():
    company = CompanyFactory.create(
        usual_name=f"Comp with Software", siren=f"00000405"
    )

    client = OAuth2ClientFactory.create(name="Mob Software", secret="password")

    ph = PasswordHasher()
    token_hash = ph.hash(API_KEY)
    ThirdPartyApiKeyFactory.create(client_id=client.id, api_key=token_hash)

    ThirdPartyClientCompanyFactory.create(
        company_id=company.id, client_id=client.id
    )

    client2 = OAuth2ClientFactory.create(
        name="Mob Software 2", secret="password"
    )

    ThirdPartyClientCompanyFactory.create(
        company_id=company.id, client_id=client2.id
    )

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password="password",
        first_name="Admin",
        last_name="Third",
    )

    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )

    for i, employee_email in enumerate(
        [
            EMPLOYEE_NOT_INVITED_EMAIL,
            EMPLOYEE_INVITED_EMAIL,
            EMPLOYEE_DISMISSED_EMAIL,
            EMPLOYEE_CONFIRMED_EMAIL,
        ]
    ):
        employee = UserFactory.create(
            email=employee_email,
            password="password",
            first_name=f"Empl{i+1}",
            last_name=f"Third",
        )
        employment = EmploymentFactory.create(
            company=company,
            submitter=admin,
            user=employee,
            has_admin_rights=False,
        )
        if employee_email != EMPLOYEE_NOT_INVITED_EMAIL:
            ThirdPartyClientEmploymentFactory.create(
                employment_id=employment.id,
                client_id=client.id,
                invitation_token="123"
                if employee_email == EMPLOYEE_INVITED_EMAIL
                else None,
                access_token="456"
                if employee_email
                in [EMPLOYEE_CONFIRMED_EMAIL, EMPLOYEE_DISMISSED_EMAIL]
                else None,
                dismissed_at=datetime.now()
                if employee_email == EMPLOYEE_DISMISSED_EMAIL
                else None,
                dismiss_author_id=admin.id
                if employee_email == EMPLOYEE_DISMISSED_EMAIL
                else None,
            )

    ThirdPartyClientEmploymentFactory.create(
        employment_id=employment.id,
        client_id=client2.id,
        access_token="789",
    )
