from argon2 import PasswordHasher

from app.helpers.oauth.models import OAuth2Client
from app.seed.factories import ThirdPartyApiKeyFactory
from app.tests import BaseTest
from app.tests.helpers import (
    INVALID_API_KEY_MESSAGE,
    ApiRequests,
    make_protected_request,
)


class TestApiSoftwareRegistration(BaseTest):
    def setUp(self):
        super().setUp()

        oauth2_client = OAuth2Client.create_client(
            name="test", redirect_uris="http://localhost:3000"
        )
        print(oauth2_client)
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

    def test_software_registration_fails_with_no_client_id(self):
        software_registration_response = make_protected_request(
            query=ApiRequests.software_registration,
            variables=dict(
                client_id=self.client_id,
                usual_name="Test",
                siren="123456789",
            ),
            headers={},
        )
        error_message = software_registration_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_software_registration_fails_with_wrong_client_id(self):
        software_registration_response = make_protected_request(
            query=ApiRequests.software_registration,
            variables=dict(
                client_id=self.client_id,
                usual_name="Test",
                siren="123456789",
            ),
            headers={
                "X-CLIENT-ID": "123",
            },
        )
        error_message = software_registration_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_software_registration_fails_with_no_api_key(self):
        software_registration_response = make_protected_request(
            query=ApiRequests.software_registration,
            variables=dict(
                client_id=self.client_id, usual_name="Test", siren="123456789"
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                # No API Key
            },
        )
        error_message = software_registration_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_software_registration_fails_with_no_prefixed_api_key(self):
        software_registration_response = make_protected_request(
            query=ApiRequests.software_registration,
            variables=dict(
                client_id=self.client_id, usual_name="Test", siren="123456789"
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-API-KEY": self.api_key,  # No prefix
            },
        )
        error_message = software_registration_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_software_registration_fails_with_wrong_api_key(self):
        software_registration_response = make_protected_request(
            query=ApiRequests.software_registration,
            variables=dict(
                client_id=self.client_id, usual_name="Test", siren="123456789"
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-API-KEY": "mobilic_live_wrong",
            },
        )
        error_message = software_registration_response["errors"][0]["message"]
        self.assertEqual(INVALID_API_KEY_MESSAGE, error_message)

    def test_software_registration_succeed(self):
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
