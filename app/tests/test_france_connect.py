from unittest import expectedFailure
from unittest.mock import patch
import jwt
import re
from urllib.parse import unquote, quote
from app.seed import UserFactory
from app.tests import BaseTest, test_post_graphql_unexposed
from app import app
from config import (
    DevConfig,
    StagingConfig,
    TestConfig,
    ProdConfig,
    SandboxConfig,
)


FC_V2_CONFIG = (
    "https://fcp-low.sbx.dev-franceconnect.fr",
    "test_client_v2",
    "test_secret_v2",
    "v2",
    10,
)

EXPECTED_DOMAINS = {
    "dev": {
        "localhost",
        "127.0.0.1",
        "testdev.localhost",
        "mobilic.preprod.beta.gouv.fr",
    },
    "staging": {"mobilic.preprod.beta.gouv.fr"},
    "test": {"localhost", "127.0.0.1", "testdev.localhost"},
    "prod": {"mobilic.beta.gouv.fr"},
    "sandbox": {"mobilic.preprod.beta.gouv.fr"},
}


class TestFranceConnect(BaseTest):
    """FranceConnect V2-only tests following Simple Code principles"""

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

    def _mock_fc_config(self, mock_config, mock_validate):
        mock_config.return_value = FC_V2_CONFIG
        mock_validate.return_value = True

    def _extract_state_data(self, location):
        state_match = re.search(r"state=([^&]+)", location)
        if not state_match:
            return None
        state_encoded = unquote(state_match.group(1))
        return jwt.decode(
            state_encoded, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
        )

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_authorize_url")
    def test_v2_connection(self, mock_validate, mock_config):
        self._mock_fc_config(mock_config, mock_validate)

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
    def test_v2_logout(self, mock_validate, mock_config):
        self._mock_fc_config(mock_config, mock_validate)

        with app.test_client() as client:
            client.set_cookie(
                domain="localhost", key="fct", value="test_token_hint"
            )
            response = client.get("/fc/logout")

        self.assertEqual(response.status_code, 302)
        location = response.headers["Location"]
        self.assertIn("/api/v2/session/end", location)
        self.assertIn("id_token_hint=test_token_hint", location)

    def test_dev_domain_config(self):
        app.config.from_object(DevConfig)
        domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        self.assertEqual(domains, EXPECTED_DOMAINS["dev"])

    def test_staging_domain_config(self):
        app.config.from_object(StagingConfig)
        domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        self.assertEqual(domains, EXPECTED_DOMAINS["staging"])

    def test_test_domain_config(self):
        app.config.from_object(TestConfig)
        domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        self.assertEqual(domains, EXPECTED_DOMAINS["test"])

    def test_prod_domain_config(self):
        app.config.from_object(ProdConfig)
        domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        self.assertEqual(domains, EXPECTED_DOMAINS["prod"])

    def test_sandbox_domain_config(self):
        app.config.from_object(SandboxConfig)
        domains = app.config.get("TRUSTED_REDIRECT_DOMAINS", set())
        self.assertEqual(domains, EXPECTED_DOMAINS["sandbox"])

    def test_environment_domain_configuration(self):
        """Legacy test method - runs all environment configs"""
        self.test_dev_domain_config()
        self.test_staging_domain_config()
        self.test_test_domain_config()
        self.test_prod_domain_config()
        self.test_sandbox_domain_config()

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_authorize_url")
    def test_jwt_state_with_context(self, mock_validate, mock_config):
        self._mock_fc_config(mock_config, mock_validate)

        redirect_uri = "https://example.com/fc-callback?context=signup&next=/dashboard&invite_token=abc123&create=true"

        with app.test_client() as client:
            response = client.get(
                f"/fc/authorize?redirect_uri={quote(redirect_uri)}"
            )

        location = response.headers["Location"]
        state_data = self._extract_state_data(location)

        self.assertIsNotNone(state_data)
        self.assertEqual(state_data["context"], "signup")
        self.assertEqual(state_data["next"], "/dashboard")
        self.assertEqual(state_data["invite_token"], "abc123")
        self.assertTrue(state_data["create"])

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_authorize_url")
    def test_jwt_state_minimal(self, mock_validate, mock_config):
        self._mock_fc_config(mock_config, mock_validate)

        with app.test_client() as client:
            response = client.get(
                "/fc/authorize?redirect_uri=https://example.com/fc-callback"
            )

        location = response.headers["Location"]
        state_data = self._extract_state_data(location)

        self.assertIsNotNone(state_data)
        self.assertEqual(state_data["context"], "login")
        self.assertIsNone(state_data["next"])
        self.assertIsNone(state_data["invite_token"])
        self.assertFalse(state_data["create"])

    @patch("app.helpers.france_connect.requests.post")
    @patch("app.helpers.france_connect.requests.get")
    @patch("app.helpers.france_connect.PyJWKClient")
    def test_ultra_simple_implementation(self, mock_jwks, mock_get, mock_post):
        from app.helpers.france_connect import get_fc_user_info

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "access_token": "test_access_token",
            "id_token": "test_id_token",
        }

        mock_get.return_value.status_code = 200
        mock_get.return_value.content.decode.return_value = "test_jwt_token"

        mock_signing_key = (
            mock_jwks.return_value.get_signing_key_from_jwt.return_value
        )
        mock_signing_key.key = "test_signing_key"

        expected_user_info = {
            "sub": "test_sub",
            "given_name": "John",
            "family_name": "Doe",
            "email": "john.doe@example.com",
        }

        with patch("app.helpers.france_connect.jwt.decode") as mock_jwt:
            mock_jwt.side_effect = [expected_user_info, {"acr": "eidas1"}]

            user_info, id_token = get_fc_user_info(
                "test_auth_code", "https://example.com/fc-callback"
            )

        self.assertEqual(user_info, expected_user_info)
        self.assertEqual(user_info["acr"], "eidas1")
        self.assertEqual(id_token, "test_id_token")

    @patch("app.controllers.user.get_fc_config")
    @patch("app.controllers.user._validate_fc_authorize_url")
    def test_v2_jwt_state_expiration(self, mock_validate, mock_config):
        """Test JWT state expiration validation"""
        self._mock_fc_config(mock_config, mock_validate)

        with app.test_client() as client:
            response = client.get(
                "/fc/authorize?redirect_uri=https://example.com/fc-callback"
            )

        location = response.headers["Location"]
        state_data = self._extract_state_data(location)

        import time

        current_time = int(time.time())
        exp_time = state_data["exp"] if state_data else current_time + 300

        self.assertGreater(exp_time, current_time)
        self.assertLessEqual(exp_time - current_time, 600)


FRANCE_CONNECT_LOGIN_MUTATION = """
    mutation ($code: String!, $state: String!, $uri: String!) {
        auth {
            franceConnectLogin(
                authorizationCode: $code
                state: $state
                originalRedirectUri: $uri
            ) {
                accessToken
                refreshToken
            }
        }
    }
"""


class TestFranceConnectStateBinding(BaseTest):
    def _mint_state_from_public_authorize_endpoint(self):
        with patch(
            "app.controllers.user.get_fc_config", return_value=FC_V2_CONFIG
        ), patch(
            "app.controllers.user._validate_fc_authorize_url",
            return_value=True,
        ):
            with app.test_client() as attacker_client:
                response = attacker_client.get(
                    "/fc/authorize?redirect_uri=https://mobilic.beta.gouv.fr/fc-callback"
                )
        location = response.headers["Location"]
        state_match = re.search(r"state=([^&]+)", location)
        self.assertIsNotNone(state_match)
        return unquote(state_match.group(1))

    @patch("app.controllers.user.get_user_from_fc_info")
    @patch("app.controllers.user.get_fc_user_info")
    def test_replayed_state_without_originating_context_is_rejected(
        self, mock_fc_user_info, mock_get_user
    ):
        """AB4 [High] FranceConnect state csrf field is never bound to the emitting request."""
        state = self._mint_state_from_public_authorize_endpoint()

        attacker_account = UserFactory.create(password="password123!")
        mock_fc_user_info.return_value = (
            {"sub": "attacker-fc-sub"},
            "fake-fc-id-token",
        )
        mock_get_user.return_value = attacker_account

        response = test_post_graphql_unexposed(
            FRANCE_CONNECT_LOGIN_MUTATION,
            variables=dict(
                code="attacker-authorization-code",
                state=state,
                uri="https://mobilic.beta.gouv.fr/fc-callback",
            ),
        )

        self.assertIsNotNone(
            response.json.get("errors"),
            "A state minted by a third party and replayed in a browser "
            "that never initiated /fc/authorize must be rejected "
            "(login CSRF protection)",
        )
        self.assertIsNone(response.json["data"]["auth"]["franceConnectLogin"])
        set_cookies = ";".join(response.headers.getlist("Set-Cookie"))
        self.assertNotIn("at=", set_cookies)
        self.assertNotIn("userId=", set_cookies)


class TestFranceConnectLoginStateValidation(BaseTest):
    def setUp(self):
        super().setUp()
        self.user = UserFactory.create(
            password="0rigPass!word", france_connect_id="fc-sub-af3"
        )

    @patch("app.controllers.user.get_fc_user_info")
    def test_invalid_state_signature_rejects_login(self, mock_fc_user_info):
        """AF3 [High]: a state with an invalid signature must abort the FranceConnect login flow."""
        mock_fc_user_info.return_value = ({"sub": "fc-sub-af3"}, "fc-token")
        forged_state = jwt.encode(
            {"csrf": "attacker", "create": False},
            "attacker-secret",
            algorithm="HS256",
        )

        response = test_post_graphql_unexposed(
            """
            mutation ($authorizationCode: String!, $state: String!, $originalRedirectUri: String!) {
                auth {
                    franceConnectLogin(
                        authorizationCode: $authorizationCode
                        state: $state
                        originalRedirectUri: $originalRedirectUri
                    ) {
                        accessToken
                        refreshToken
                    }
                }
            }
            """,
            variables=dict(
                authorizationCode="fake-code",
                state=forged_state,
                originalRedirectUri="https://localhost/fc-callback",
            ),
        )

        self.assertIsNotNone(response.json.get("errors"))
        mock_fc_user_info.assert_not_called()
