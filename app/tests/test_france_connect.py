from unittest.mock import patch
import jwt
import re
from urllib.parse import unquote, quote
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
                "JWT_SECRET_KEY": "test-jwt-secret-key",
                "FC_TIMEOUT": 10,
                "MOBILIC_ENV": "test",
            }
        )

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

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_authorize_url")
    def test_v2_jwt_state_with_context(
        self, mock_validate_url, mock_get_fc_config
    ):
        """Test V2 FranceConnect with JWT state containing context parameters"""
        mock_get_fc_config.return_value = (
            "https://fcp-low.sbx.dev-franceconnect.fr",
            "test_client_v2",
            "test_secret_v2",
            "v2",
            10,
        )
        mock_validate_url.return_value = True

        with app.test_client() as client:
            # Test with all context parameters
            redirect_uri = "https://example.com/fc-callback?context=signup&next=/dashboard&invite_token=abc123&create=true"
            response = client.get(
                f"/fc/authorize?redirect_uri={quote(redirect_uri)}"
            )

        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]

        # Extract state from redirect URL
        state_match = re.search(r"state=([^&]+)", location)
        self.assertIsNotNone(
            state_match, "State parameter not found in redirect URL"
        )

        state_encoded = unquote(state_match.group(1))

        # Decode JWT state
        state_data = jwt.decode(
            state_encoded, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
        )

        # Verify JWT state contains all context parameters
        self.assertIn("csrf", state_data)
        self.assertGreaterEqual(
            len(state_data["csrf"]), 32, "CSRF token must be at least 32 chars"
        )
        self.assertEqual(state_data["context"], "signup")
        self.assertEqual(state_data["next"], "/dashboard")
        self.assertEqual(state_data["invite_token"], "abc123")
        self.assertTrue(state_data["create"])
        self.assertIn("exp", state_data)

        # Verify clean redirect_uri without parameters
        self.assertIn(
            "redirect_uri=https%3A%2F%2Fexample.com%2Ffc-callback", location
        )
        self.assertNotIn("context%3D", location)
        self.assertNotIn("next%3D", location)
        self.assertNotIn("invite_token%3D", location)

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_authorize_url")
    def test_v2_jwt_state_minimal(self, mock_validate_url, mock_get_fc_config):
        """Test V2 FranceConnect with minimal JWT state"""
        mock_get_fc_config.return_value = (
            "https://fcp-low.sbx.dev-franceconnect.fr",
            "test_client_v2",
            "test_secret_v2",
            "v2",
            10,
        )
        mock_validate_url.return_value = True

        with app.test_client() as client:
            # Test with minimal parameters
            response = client.get(
                "/fc/authorize?redirect_uri=https://example.com/fc-callback"
            )

        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]

        # Extract and decode state
        state_match = re.search(r"state=([^&]+)", location)
        self.assertIsNotNone(state_match)

        state_encoded = unquote(state_match.group(1))
        state_data = jwt.decode(
            state_encoded, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
        )

        # Verify default values in JWT state
        self.assertEqual(state_data["context"], "login")
        self.assertIsNone(state_data["next"])
        self.assertIsNone(state_data["invite_token"])
        self.assertFalse(state_data["create"])

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_authorize_url")
    def test_v2_jwt_state_expiration(
        self, mock_validate_url, mock_get_fc_config
    ):
        """Test JWT state expiration validation"""
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
                "/fc/authorize?redirect_uri=https://example.com/fc-callback"
            )

        # Extract state
        location = response.headers["Location"]
        state_match = re.search(r"state=([^&]+)", location)
        state_encoded = unquote(state_match.group(1))

        # Decode to check expiration
        state_data = jwt.decode(
            state_encoded, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
        )

        import time

        current_time = int(time.time())
        exp_time = state_data["exp"]

        # Verify expiration is set to 10 minutes in the future
        self.assertGreater(exp_time, current_time)
        self.assertLessEqual(exp_time - current_time, 600)  # 10 minutes
