from datetime import datetime, timedelta
from freezegun import freeze_time
from time import sleep

from app.tests import BaseTest, test_post_graphql
from app import app, db
from app.seed import UserFactory
from app.tests.helpers import ApiRequests


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

            reuse_refresh_token_response = test_post_graphql(
                self.refresh_query,
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response_data['refreshToken']}",
                    )
                ],
            )
            self.assertIsNotNone(
                reuse_refresh_token_response.json.get("errors")
            )
            self.assertIsNone(
                reuse_refresh_token_response.json["data"]["auth"]["refresh"]
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
