from datetime import date, datetime
from argon2 import PasswordHasher

from app.helpers.oauth.models import OAuth2Client
from app.models.company import Company
from app.seed.factories import (
    EmploymentFactory,
    ThirdPartyApiKeyFactory,
    UserFactory,
)
from app.tests import BaseTest
from app.tests.helpers import (
    INVALID_API_KEY_MESSAGE,
    ApiRequests,
    make_protected_request,
)


employee1 = {
    "firstName": "Prénom_test1",
    "lastName": "Nom_test1",
    "email": "email-salarie1@example.com",
}


class TestApiSyncEmployment(BaseTest):
    def setUp(self):
        super().setUp()

        oauth2_client = OAuth2Client.create_client(
            name="test", redirect_uris="http://localhost:3000"
        )
        self.assertIsNotNone(oauth2_client)
        self.client_id = oauth2_client.get_client_id()
        self.client_secret = oauth2_client.secret
        self.api_key = (
            "012345678901234567890123456789012345678901234567890123456789"
        )

        ph = PasswordHasher()
        ThirdPartyApiKeyFactory.create(
            client=oauth2_client, api_key=ph.hash(self.api_key)
        )

        software_registration_response = make_protected_request(
            query=ApiRequests.software_registration,
            variables=dict(
                client_id=self.client_id, usual_name="Test", siren="123456789"
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-API-KEY": "mobilic_live_" + self.api_key,
            },
        )
        company_id = software_registration_response["data"]["company"][
            "softwareRegistration"
        ]["id"]
        self.assertIsNotNone(company_id)
        self.company_id = company_id

    def test_sync_employments_fails_with_no_client_id(self):
        sync_employment_response = make_protected_request(
            query=ApiRequests.sync_employment,
            variables=dict(
                company_id=self.company_id,
                employees=[employee1],
            ),
            headers={},
        )
        error_message = sync_employment_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_sync_employments_fails_with_wrong_client_id(self):
        sync_employment_response = make_protected_request(
            query=ApiRequests.sync_employment,
            variables=dict(
                company_id=self.company_id,
                employees=[employee1],
            ),
            headers={
                "X-CLIENT-ID": "123",
            },
        )
        error_message = sync_employment_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_sync_employments_fails_with_no_api_key(self):
        sync_employment_response = make_protected_request(
            query=ApiRequests.sync_employment,
            variables=dict(
                company_id=self.company_id,
                employees=[employee1],
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                # No API Key
            },
        )
        error_message = sync_employment_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_sync_employments_fails_with_wrong_api_key(self):
        sync_employment_response = make_protected_request(
            query=ApiRequests.sync_employment,
            variables=dict(
                company_id=self.company_id,
                employees=[employee1],
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-API-KEY": "mobilic_live_wrong",
            },
        )
        error_message = sync_employment_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_sync_employments_succeed(self):
        sync_employment_response = make_protected_request(
            query=ApiRequests.sync_employment,
            variables=dict(
                company_id=self.company_id,
                employees=[
                    employee1,
                    {
                        "firstName": "Prénom_test2",
                        "lastName": "Nom_test2",
                        "email": "email-salarie2@example.com",
                    },
                ],
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-API-KEY": "mobilic_live_" + self.api_key,
            },
        )
        employment_ids = sync_employment_response["data"]["company"][
            "syncEmployment"
        ]
        self.assertEqual(len(employment_ids), 2)

    def test_sync_employments_already_exists(self):
        company = Company.query.get(self.company_id)
        existing_employee = UserFactory.create(
            first_name="Existing", last_name="Employee", post__company=company
        )
        sync_employment_response = make_protected_request(
            query=ApiRequests.sync_employment,
            variables=dict(
                company_id=self.company_id,
                employees=[
                    employee1,
                    {
                        "firstName": existing_employee.first_name,
                        "lastName": existing_employee.last_name,
                        "email": existing_employee.email,
                    },
                ],
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-API-KEY": "mobilic_live_" + self.api_key,
            },
        )
        employment_ids = sync_employment_response["data"]["company"][
            "syncEmployment"
        ]
        self.assertEqual(len(employment_ids), 2)
        self.assertIsNotNone(employment_ids[0]["email"])
        self.assertIsNotNone(employment_ids[1]["email"])

    def test_sync_employments_many_already_exists(self):
        company = Company.query.get(self.company_id)
        existing_employee = UserFactory.create(
            first_name="Existing",
            last_name="Employee",
            post__company=company,
            post__start_date=date(2024, 1, 1),
        )
        EmploymentFactory.create(
            company=company,
            submitter=existing_employee,
            user=existing_employee,
            has_admin_rights=False,
            start_date=date(2023, 1, 1),
            end_date=datetime(2023, 6, 1),
        )
        sync_employment_response = make_protected_request(
            query=ApiRequests.sync_employment,
            variables=dict(
                company_id=self.company_id,
                employees=[
                    {
                        "firstName": existing_employee.first_name,
                        "lastName": existing_employee.last_name,
                        "email": existing_employee.email,
                    },
                ],
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-API-KEY": "mobilic_live_" + self.api_key,
            },
        )
        employment_ids = sync_employment_response["data"]["company"][
            "syncEmployment"
        ]
        self.assertEqual(len(employment_ids), 1)
