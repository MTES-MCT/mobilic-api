from unittest.mock import patch
from app.tests import BaseTest
from app import app
from config import (
    DevConfig,
    StagingConfig,
    TestConfig,
    ProdConfig,
    SandboxConfig,
)


class TestFranceConnect(BaseTest):
    """FranceConnect connection and logout tests for each environment"""

    def setUp(self):
        super().setUp()
        app.config.update(
            {
                "SECRET_KEY": "test-secret-key",
                "FC_TIMEOUT": 10,
                "MOBILIC_ENV": "test",
            }
        )

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_authorize_url")
    def test_v1_connection(self, mock_validate_url, mock_get_fc_config):
        """Test V1 FranceConnect authorization redirect"""
        mock_get_fc_config.return_value = (
            "https://fcp.integ01.dev-franceconnect.fr",
            "test_client_v1",
            "test_secret_v1",
            "v1",
            10,
        )
        mock_validate_url.return_value = True

        with app.test_client() as client:
            response = client.get(
                "/fc/authorize?redirect_uri=https://example.com/callback"
            )

        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]
        self.assertIn("/api/v1/authorize", location)
        self.assertIn("client_id=test_client_v1", location)
        self.assertIn(
            "scope=openid%20email%20given_name%20family_name%20preferred_username%20birthdate",
            location,
        )
        self.assertIn("response_type=code", location)
        self.assertIn("acr_values=eidas1", location)

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_authorize_url")
    def test_v2_connection(self, mock_validate_url, mock_get_fc_config):
        """Test V2 FranceConnect authorization redirect"""
        mock_get_fc_config.return_value = (
            "https://fcp-low.sbx.dev-franceconnect.fr",
            "test_client_v2",
            "test_secret_v2",
            "v2",
            10,
        )
        mock_validate_url.return_value = True

        with app.test_client() as client:
            response = client.get(
                "/fc/authorize?redirect_uri=https://example.com/callback"
            )

        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]
        self.assertIn("/api/v2/authorize", location)
        self.assertIn("client_id=test_client_v2", location)

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_logout_url")
    def test_v1_logout(self, mock_validate_url, mock_get_fc_config):
        """Test V1 FranceConnect logout redirect"""
        mock_get_fc_config.return_value = (
            "https://fcp.integ01.dev-franceconnect.fr",
            "test_client_v1",
            "test_secret_v1",
            "v1",
            10,
        )
        mock_validate_url.return_value = True

        with app.test_client() as client:
            client.set_cookie(
                domain="localhost", key="fct", value="test_token_hint"
            )
            response = client.get("/fc/logout")

        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]
        self.assertIn("/api/v1/logout", location)
        self.assertIn("id_token_hint=test_token_hint", location)

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_logout_url")
    def test_v2_logout(self, mock_validate_url, mock_get_fc_config):
        """Test V2 FranceConnect logout redirect"""
        mock_get_fc_config.return_value = (
            "https://fcp-low.sbx.dev-franceconnect.fr",
            "test_client_v2",
            "test_secret_v2",
            "v2",
            10,
        )
        mock_validate_url.return_value = True

        with app.test_client() as client:
            client.set_cookie(
                domain="localhost", key="fct", value="test_token_hint"
            )
            response = client.get("/fc/logout")

        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]
        self.assertIn("/api/v2/session/end", location)
        self.assertIn("id_token_hint=test_token_hint", location)
        self.assertIn("post_logout_redirect_uri=", location)

    def test_environment_domain_configuration(self):
        """Test that each environment configuration loads proper trusted domains"""
        app.config.from_object(DevConfig)
        dev_domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        self.assertIn("localhost", dev_domains)
        self.assertIn("127.0.0.1", dev_domains)
        self.assertIn("testdev.localhost", dev_domains)
        self.assertIn("mobilic.beta.gouv.fr", dev_domains)
        self.assertIn("mobilic.preprod.beta.gouv.fr", dev_domains)

        app.config.from_object(StagingConfig)
        staging_domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        expected_staging_domains = {
            "mobilic.preprod.beta.gouv.fr",
        }
        self.assertEqual(staging_domains, expected_staging_domains)

        app.config.from_object(TestConfig)
        test_domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        self.assertIn("localhost", test_domains)
        self.assertIn("127.0.0.1", test_domains)
        self.assertIn("testdev.localhost", test_domains)

        app.config.from_object(ProdConfig)
        prod_domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        self.assertEqual(prod_domains, {"mobilic.beta.gouv.fr"})

        app.config.from_object(SandboxConfig)
        sandbox_domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        self.assertIn("mobilic.beta.gouv.fr", sandbox_domains)
        self.assertIn("mobilic.preprod.beta.gouv.fr", sandbox_domains)
