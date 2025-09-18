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
        # print(oauth2_client)
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

    def test_software_registration_fails_with_existing_global_company(self):
        """Test that creating specific establishments fails when a global company exists for the SIREN"""
        from app.models import Company
        from app import db

        test_siren = "987654321"

        # Create a global company (no specific SIRETs)
        global_company = Company(
            usual_name="Global Test Company",
            siren=test_siren,
            short_sirets=[],
            allow_team_mode=True,
            allow_transfers=False,
            require_kilometer_data=True,
            require_support_activity=False,
            require_mission_name=True,
        )
        db.session.add(global_company)
        db.session.commit()

        software_registration_response = make_protected_request(
            query=ApiRequests.software_registration,
            variables=dict(
                client_id=self.client_id,
                usual_name="Test Establishment",
                siren=test_siren,
                siret=f"{test_siren}12345",
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-API-KEY": "mobilic_live_" + self.api_key,
            },
        )

        self.assertIn("errors", software_registration_response)
        error = software_registration_response["errors"][0]
        self.assertEqual(
            error["extensions"]["code"], "SIREN_ALREADY_SIGNED_UP"
        )
        self.assertIn("globally for this SIREN", error["message"])

    def test_software_registration_succeeds_with_different_sirets_same_siren(
        self,
    ):
        """Test that creating different establishments succeeds when no conflict exists"""
        from app.models import Company
        from app import db

        test_siren = "123987654"

        # Create a company with specific SIRET
        existing_company = Company(
            usual_name="Existing Establishment",
            siren=test_siren,
            short_sirets=[12345],
            allow_team_mode=True,
            allow_transfers=False,
            require_kilometer_data=True,
            require_support_activity=False,
            require_mission_name=True,
        )
        db.session.add(existing_company)
        db.session.commit()

        software_registration_response = make_protected_request(
            query=ApiRequests.software_registration,
            variables=dict(
                client_id=self.client_id,
                usual_name="New Establishment",
                siren=test_siren,
                siret=f"{test_siren}67890",
            ),
            headers={
                "X-CLIENT-ID": self.client_id,
                "X-API-KEY": "mobilic_live_" + self.api_key,
            },
        )

        self.assertNotIn("errors", software_registration_response)
        self.assertIn("data", software_registration_response)
        company_id = software_registration_response["data"]["company"][
            "softwareRegistration"
        ]["id"]
        self.assertIsNotNone(company_id)
