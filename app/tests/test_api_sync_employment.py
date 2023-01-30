from argon2 import PasswordHasher

from app.helpers.oauth.models import OAuth2Client
from app.seed.factories import ThirdPartyApiKeyFactory
from app.tests import BaseTest
from app.tests.helpers import ApiRequests, make_protected_request

INVALID_API_KEY_MESSAGE = "Invalid API Key"


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
                employees=[
                    {
                        "firstName": "Prénom_test1",
                        "lastName": "Nom_test1",
                        "email": "email-salarie1@example.com",
                    }
                ],
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
                employees=[
                    {
                        "firstName": "Prénom_test1",
                        "lastName": "Nom_test1",
                        "email": "email-salarie1@example.com",
                    }
                ],
            ),
            headers={
                "X-CLIENT-ID": "wrong",
            },
        )
        error_message = sync_employment_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_sync_employments_fails_with_no_api_key(self):
        sync_employment_response = make_protected_request(
            query=ApiRequests.sync_employment,
            variables=dict(
                company_id=self.company_id,
                employees=[
                    {
                        "firstName": "Prénom_test1",
                        "lastName": "Nom_test1",
                        "email": "email-salarie1@example.com",
                    }
                ],
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
                employees=[
                    {
                        "firstName": "Prénom_test1",
                        "lastName": "Nom_test1",
                        "email": "email-salarie1@example.com",
                    }
                ],
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
                    {
                        "firstName": "Prénom_test1",
                        "lastName": "Nom_test1",
                        "email": "email-salarie1@example.com",
                    },
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
