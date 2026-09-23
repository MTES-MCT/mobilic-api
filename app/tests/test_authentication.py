import os
import subprocess
import sys
from datetime import datetime, timedelta
from flask_jwt_extended import decode_token
from freezegun import freeze_time
from time import sleep
from unittest import TestCase, expectedFailure
from unittest.mock import patch

import config
from app.tests import BaseTest, test_post_graphql, test_post_graphql_unexposed
from app import app, db
from app.seed import ControllerUserFactory, UserFactory
from app.tests.helpers import ApiRequests

API_ROOT = os.path.dirname(config.__file__)


class TestAuthentication(BaseTest):
    def setUp(self):
        super().setUp()
        self.user = UserFactory.create(password="passwd")

        self.refresh_query = """
            mutation {
                    auth {
                        refresh {
                            accessToken
                            refreshToken
                        }
                    }
                }
            """

        self.check_query = """
            query {
                    checkAuth {
                        success
                        userId
                    }
                }
            """

    def test_login_fails_on_wrong_email(self):
        login_response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email="random-junk", password="passwd"),
        )
        self.assertEqual(400, login_response.status_code)

        login_response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email="testt@test.test", password="passwd"),
        )
        self.assertIsNotNone(login_response.json.get("errors"))
        self.assertIsNone(login_response.json["data"]["auth"]["login"])

    def test_login_fails_on_wrong_password(self):
        login_response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email=self.user.email, password="passw"),
        )
        self.assertIsNotNone(login_response.json.get("errors"))
        self.assertIsNone(login_response.json["data"]["auth"]["login"])

        login_response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email=self.user.email, password="passwdd"),
        )
        self.assertIsNotNone(login_response.json.get("errors"))
        self.assertIsNone(login_response.json["data"]["auth"]["login"])

        login_response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email="random-junk", password="passwdd"),
        )
        self.assertEqual(400, login_response.status_code)

    def test_auth_token_flow_works_correctly(self):
        base_time = datetime.now()
        # Step 1 : login
        with freeze_time(base_time):
            login_response = test_post_graphql(
                ApiRequests.login_query,
                variables=dict(email=self.user.email, password="passwd"),
            )
            self.assertEqual(login_response.status_code, 200)
            login_response_data = login_response.json["data"]["auth"]["login"]
            self.assertIn("accessToken", login_response_data)
            self.assertIn("refreshToken", login_response_data)

        # Step 2 : access protected endpoint within token expiration time
        with freeze_time(base_time + timedelta(seconds=30)):
            access_response = test_post_graphql(
                self.check_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response_data['accessToken']}",
                    )
                ],
            )
            self.assertEqual(access_response.status_code, 200)
            access_response_data = access_response.json["data"]["checkAuth"]
            self.assertEqual(access_response_data["userId"], self.user.id)

        # Refresh access token after expiration
        with freeze_time(
            base_time
            + timedelta(minutes=10)
            + app.config["ACCESS_TOKEN_EXPIRATION"]
        ):
            expired_access_response = test_post_graphql(
                self.check_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response_data['accessToken']}",
                    )
                ],
            )
            self.assertIsNotNone(expired_access_response.json.get("errors"))
            self.assertIsNone(expired_access_response.json["data"])

            refresh_response = test_post_graphql(
                self.refresh_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response_data['refreshToken']}",
                    )
                ],
            )
            self.assertEqual(refresh_response.status_code, 200)
            refresh_response_data = refresh_response.json["data"]["auth"][
                "refresh"
            ]
            self.assertIn("accessToken", refresh_response_data)
            self.assertIn("refreshToken", refresh_response_data)

            new_access_response = test_post_graphql(
                self.check_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {refresh_response_data['accessToken']}",
                    )
                ],
            )
            self.assertEqual(new_access_response.status_code, 200)
            new_access_response_data = new_access_response.json["data"][
                "checkAuth"
            ]
            self.assertEqual(new_access_response_data["userId"], self.user.id)

            # Replay within the reuse grace period : reissues the successor
            # tokens instead of failing (lost response, concurrent tabs)
            reuse_refresh_token_response = test_post_graphql(
                self.refresh_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response_data['refreshToken']}",
                    )
                ],
            )
            self.assertIsNone(reuse_refresh_token_response.json.get("errors"))
            replayed_data = reuse_refresh_token_response.json["data"]["auth"][
                "refresh"
            ]
            self.assertEqual(
                decode_token(replayed_data["refreshToken"])["identity"][
                    "token"
                ],
                decode_token(refresh_response_data["refreshToken"])[
                    "identity"
                ]["token"],
            )

        # Replay beyond the grace period : reuse detection revokes the
        # whole descendant chain
        with freeze_time(
            base_time
            + timedelta(minutes=15)
            + app.config["ACCESS_TOKEN_EXPIRATION"]
        ):
            late_reuse_response = test_post_graphql(
                self.refresh_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response_data['refreshToken']}",
                    )
                ],
            )
            self.assertIsNotNone(late_reuse_response.json.get("errors"))
            self.assertIsNone(
                late_reuse_response.json["data"]["auth"]["refresh"]
            )

            revoked_successor_response = test_post_graphql(
                self.refresh_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {refresh_response_data['refreshToken']}",
                    )
                ],
            )
            self.assertIsNotNone(revoked_successor_response.json.get("errors"))
            self.assertIsNone(
                revoked_successor_response.json["data"]["auth"]["refresh"]
            )

    def test_access_fails_on_bad_token(self):
        base_time = datetime.now()
        # Step 1 : login
        with freeze_time(base_time):
            login_response = test_post_graphql(
                ApiRequests.login_query,
                variables=dict(email=self.user.email, password="passwd"),
            )
            self.assertEqual(login_response.status_code, 200)
            login_response_data = login_response.json["data"]["auth"]["login"]
            self.assertIn("accessToken", login_response_data)
            self.assertIn("refreshToken", login_response_data)

        with freeze_time(base_time + timedelta(seconds=30)):
            wrong_access_response = test_post_graphql(
                self.check_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response_data['accessToken']}abc",
                    )
                ],
            )
            self.assertIsNotNone(wrong_access_response.json.get("errors"))
            self.assertIsNone(wrong_access_response.json["data"])

            mixing_tokens_response = test_post_graphql(
                self.check_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response_data['refreshToken']}",
                    )
                ],
            )
            self.assertIsNotNone(mixing_tokens_response.json.get("errors"))
            self.assertIsNone(mixing_tokens_response.json["data"])

    def test_refresh_fails_on_bad_token(self):
        login_response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email=self.user.email, password="passwd"),
        )
        self.assertEqual(login_response.status_code, 200)
        login_response_data = login_response.json["data"]["auth"]["login"]
        self.assertIn("accessToken", login_response_data)
        self.assertIn("refreshToken", login_response_data)

        wrong_refresh_response = test_post_graphql(
            self.refresh_query,
            headers=[
                (
                    "Authorization",
                    f"Bearer {login_response_data['refreshToken']}abc",
                )
            ],
        )
        self.assertIsNotNone(wrong_refresh_response.json.get("errors"))
        self.assertIsNone(
            wrong_refresh_response.json["data"]["auth"]["refresh"]
        )

        mixing_tokens_response = test_post_graphql(
            self.refresh_query,
            headers=[
                (
                    "Authorization",
                    f"Bearer {login_response_data['accessToken']}",
                )
            ],
        )
        self.assertIsNotNone(mixing_tokens_response.json.get("errors"))
        self.assertIsNone(
            mixing_tokens_response.json["data"]["auth"]["refresh"]
        )

    def test_tokens_fail_on_revoked_user(self):
        # Step 1 : login
        login_response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email=self.user.email, password="passwd"),
        )
        self.assertEqual(login_response.status_code, 200)
        login_response_data = login_response.json["data"]["auth"]["login"]
        self.assertIn("accessToken", login_response_data)
        self.assertIn("refreshToken", login_response_data)

        # Revoke user
        sleep(1)
        self.user.revoke_all_tokens()
        db.session.commit()

        wrong_access_response = test_post_graphql(
            self.check_query,
            headers=[
                (
                    "Authorization",
                    f"Bearer {login_response_data['accessToken']}",
                )
            ],
        )
        self.assertIsNotNone(wrong_access_response.json.get("errors"))
        self.assertIsNone(wrong_access_response.json["data"])

        wrong_refresh_response = test_post_graphql(
            self.refresh_query,
            headers=[
                (
                    "Authorization",
                    f"Bearer {login_response_data['refreshToken']}",
                )
            ],
        )
        self.assertIsNotNone(wrong_refresh_response.json.get("errors"))
        self.assertIsNone(
            wrong_refresh_response.json["data"]["auth"]["refresh"]
        )

    def test_blocking_account(self):
        for i in range(0, 10):
            login_response = test_post_graphql(
                ApiRequests.login_query,
                variables=dict(email=self.user.email, password="wrong_passwd"),
            )
        self.assertEqual(
            "BLOCKED_ACCOUNT_ERROR",
            login_response.json["errors"][0]["extensions"]["code"],
        )
        good_login_response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email=self.user.email, password="passwd"),
        )
        self.assertEqual(
            "BLOCKED_ACCOUNT_ERROR",
            good_login_response.json["errors"][0]["extensions"]["code"],
        )

    def test_reset_bad_password_counter(self):
        for i in range(0, 8):
            test_post_graphql(
                ApiRequests.login_query,
                variables=dict(email=self.user.email, password="wrong_passwd"),
            )
        test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email=self.user.email, password="passwd"),
        )
        for i in range(0, 8):
            test_post_graphql(
                ApiRequests.login_query,
                variables=dict(email=self.user.email, password="wrong_passwd"),
            )
        good_login_response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email=self.user.email, password="passwd"),
        )
        self.assertIsNotNone(
            good_login_response.json["data"]["auth"]["login"]["accessToken"]
        )


WEAK_JWT_SECRET = "my-little-secret"
HOSTILE_ORIGIN = "https://evil.example"

AGENT_CONNECT_LOGIN_MUTATION = """
    mutation ($code: String!, $state: String!, $uri: String!) {
        auth {
            agentConnectLogin(
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


class TestJwtSecretKeyFallback(TestCase):
    def _config_jwt_secret_in_subprocess(self, extra_env):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("JWT_SECRET_KEY", "DOTENV_FILE")
        }
        env.update(extra_env)
        return subprocess.run(
            [
                sys.executable,
                "-c",
                "import config; print(config.Config.JWT_SECRET_KEY)",
            ],
            capture_output=True,
            text=True,
            cwd=str(API_ROOT),
            env=env,
        )

    def test_dev_generates_strong_secret_not_weak_default(self):
        """config must not fall back to a public hardcoded JWT secret."""
        result = self._config_jwt_secret_in_subprocess({"MOBILIC_ENV": "dev"})
        self.assertEqual(0, result.returncode, result.stderr)
        secret = result.stdout.strip()
        self.assertNotEqual(secret, WEAK_JWT_SECRET)
        self.assertGreaterEqual(len(secret), 32)

    def test_real_env_refuses_to_start_without_secret(self):
        """a real environment must abort startup rather than use a default JWT secret."""
        result = self._config_jwt_secret_in_subprocess({"MOBILIC_ENV": "prod"})
        self.assertNotEqual(0, result.returncode)
        self.assertIn("JWT_SECRET_KEY", result.stderr)


class TestAgentConnectStateVerification(BaseTest):
    @patch("app.controllers.controller.get_controller_from_ac_info")
    @patch("app.controllers.controller.check_idp_allowed")
    @patch("app.controllers.controller.get_agent_connect_user_info")
    def test_forged_state_is_rejected(
        self, mock_ac_user_info, mock_check_idp, mock_get_controller
    ):
        """AgentConnectLogin ignores the state parameter entirely."""
        mock_ac_user_info.return_value = (
            {
                "sub": "attacker-ac-sub",
                "given_name": "Attacker",
                "usual_name": "Controller",
                "email": "attacker@example.com",
                "organizational_unit": "CTT",
                "idp_id": "allowed-idp",
            },
            "fake-ac-id-token",
        )
        mock_check_idp.return_value = None
        mock_get_controller.return_value = ControllerUserFactory.create(
            email="attacker-controller@example.com"
        )

        response = test_post_graphql_unexposed(
            AGENT_CONNECT_LOGIN_MUTATION,
            variables=dict(
                code="attacker-authorization-code",
                state="forged-state-never-issued-by-server",
                uri="https://mobilic.beta.gouv.fr/ac-callback",
            ),
        )

        self.assertIsNotNone(
            response.json.get("errors"),
            "A state that was never issued by /ac/authorize must be "
            "rejected (OAuth CSRF protection, RFC 6749 §10.12)",
        )
        self.assertIsNone(response.json["data"]["auth"]["agentConnectLogin"])
        set_cookies = ";".join(response.headers.getlist("Set-Cookie"))
        self.assertNotIn("controllerId=", set_cookies)
        self.assertNotIn("at=", set_cookies)


class TestCorsPolicy(TestCase):
    @expectedFailure
    def test_preflight_does_not_allow_hostile_origin(self):
        """CORS(app) at app/__init__.py:103 has no origin whitelist."""
        with app.test_client() as client:
            response = client.options(
                "/graphql",
                headers={
                    "Origin": HOSTILE_ORIGIN,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
        allow_origin = response.headers.get("Access-Control-Allow-Origin")
        self.assertNotEqual(
            allow_origin,
            "*",
            "CORS preflight must not allow all origins on /graphql",
        )
        self.assertNotEqual(
            allow_origin,
            HOSTILE_ORIGIN,
            "CORS preflight must not reflect an arbitrary hostile origin",
        )

    @expectedFailure
    def test_actual_response_does_not_allow_hostile_origin(self):
        """Cross-origin POST responses must not be readable by any site."""
        with app.test_client() as client:
            response = client.post(
                "/graphql",
                json=dict(query="{ __typename }"),
                headers={"Origin": HOSTILE_ORIGIN},
            )
        allow_origin = response.headers.get("Access-Control-Allow-Origin")
        self.assertNotEqual(
            allow_origin,
            "*",
            "GraphQL responses must not be exposed to all origins",
        )
        self.assertNotEqual(
            allow_origin,
            HOSTILE_ORIGIN,
            "GraphQL responses must not be exposed to a hostile origin",
        )


class TestDisablePasswordCheckParsing(TestCase):
    def _import_config_in_subprocess(self, env):
        return subprocess.run(
            [
                sys.executable,
                "-c",
                "import config; print(bool(config.Config.DISABLE_PASSWORD_CHECK))",
            ],
            capture_output=True,
            text=True,
            cwd=API_ROOT,
            env={**os.environ, **env},
        )

    def _parsed_flag_in_subprocess(self, env_value):
        result = self._import_config_in_subprocess(
            {"DISABLE_PASSWORD_CHECK": env_value, "MOBILIC_ENV": "test"}
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout.strip()

    def test_falsy_string_values_do_not_disable_password_check(self):
        """DISABLE_PASSWORD_CHECK=false or 0 must parse as falsy, not bypass password checks."""
        for env_value in ["false", "0", "False", "no", "  false  "]:
            with self.subTest(env_value=env_value):
                self.assertEqual(
                    "False", self._parsed_flag_in_subprocess(env_value)
                )

    def test_surrounding_whitespace_is_stripped(self):
        """A padded truthy value still disables the check in dev/test."""
        for env_value in [" true ", "\t1\n", "  yes"]:
            with self.subTest(env_value=env_value):
                self.assertEqual(
                    "True", self._parsed_flag_in_subprocess(env_value)
                )

    def test_cannot_be_enabled_outside_dev_test(self):
        """DISABLE_PASSWORD_CHECK enabled in a real environment must abort startup."""
        result = self._import_config_in_subprocess(
            {
                "DISABLE_PASSWORD_CHECK": "true",
                "MOBILIC_ENV": "prod",
                "JWT_SECRET_KEY": "isolate-the-password-check-guard",
            }
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("DISABLE_PASSWORD_CHECK", result.stderr)

    def test_enabled_flag_alone_does_not_abort_in_real_env(self):
        """A real env without the flag must still boot (guard is scoped to the flag)."""
        result = self._import_config_in_subprocess(
            {
                "DISABLE_PASSWORD_CHECK": "false",
                "MOBILIC_ENV": "prod",
                "JWT_SECRET_KEY": "isolate-the-password-check-guard",
            }
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("False", result.stdout.strip())


class TestOW8LoginUnknownEmail(BaseTest):
    @expectedFailure
    def test_unknown_email_returns_generic_error(self):
        """LoginMutation crashes with AttributeError on None."""
        response = test_post_graphql(
            query=ApiRequests.login_query,
            variables=dict(
                email="does-not-exist@example.com",
                password="whatever123!",
            ),
        ).json

        self.assertIn("errors", response)
        error = response["errors"][0]
        message = error.get("message", "")

        self.assertNotIn("NoneType", message)
        self.assertNotIn("has no attribute", message)
        self.assertEqual(
            "AUTHENTICATION_ERROR",
            error.get("extensions", {}).get("code"),
            "Unknown email must yield a generic authentication error",
        )
        self.assertIn("Wrong email/password combination", message)


class TestOW12JwtCookieCsrfProtection(TestCase):
    @expectedFailure
    def test_cookie_tokens_are_csrf_protected(self):
        """JWT cookies without CSRF protect nor SameSite."""
        from config import ProdConfig

        if "cookies" not in ProdConfig.JWT_TOKEN_LOCATION:
            self.skipTest("JWT tokens are no longer stored in cookies")

        samesite = getattr(ProdConfig, "JWT_COOKIE_SAMESITE", None)
        csrf_protected = getattr(ProdConfig, "JWT_COOKIE_CSRF_PROTECT", False)

        self.assertTrue(
            csrf_protected or samesite == "Strict",
            "Cookie-based JWTs need CSRF protection or SameSite=Strict",
        )


class TestOW20ProdAccessTokenExpiration(TestCase):
    @expectedFailure
    def test_prod_access_token_lifetime_is_short(self):
        """ProdConfig.ACCESS_TOKEN_EXPIRATION is 16h."""
        from config import ProdConfig

        self.assertLessEqual(
            ProdConfig.ACCESS_TOKEN_EXPIRATION,
            timedelta(hours=1),
            "Production access token lifetime must be at most 1 hour",
        )
