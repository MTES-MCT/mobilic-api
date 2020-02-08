from datetime import datetime, timedelta
from freezegun import freeze_time

from app.tests import BaseTest
from app import app, db
from app.models import User, Company


class TestAuth(BaseTest):
    def setUp(self):
        super().setUp()
        company = Company.create(name="world corp")
        self.user = User.create(
            email="test@test.test",
            password="passwd",
            first_name="Moby",
            last_name="Lick",
            company=company,
        )

    def test_login_fails_on_wrong_email(self):
        with app.test_client() as c:
            login_response = c.post(
                "/auth/login",
                json=dict(email="random-junk", password="passwd"),
            )
            self.assertEqual(login_response.status_code, 401)

            login_response = c.post(
                "/auth/login",
                json=dict(email="testt@test.test", password="passwd"),
            )
            self.assertEqual(login_response.status_code, 401)

    def test_login_fails_on_wrong_password(self):
        with app.test_client() as c:
            login_response = c.post(
                "/auth/login",
                json=dict(email=self.user.email, password="passwdd"),
            )
            self.assertEqual(login_response.status_code, 401)

            login_response = c.post(
                "/auth/login",
                json=dict(email=self.user.email, password="passw"),
            )
            self.assertEqual(login_response.status_code, 401)

            login_response = c.post(
                "/auth/login", json=dict(email="random-junk", password="passw")
            )
            self.assertEqual(login_response.status_code, 401)

    def test_auth_token_flow_works_correctly(self):
        base_time = datetime.now()
        with app.test_client() as c:
            # Step 1 : login
            with freeze_time(base_time):
                login_response = c.post(
                    "/auth/login",
                    json=dict(email=self.user.email, password="passwd"),
                )
                self.assertEqual(login_response.status_code, 200)

            # Step 2 : access protected endpoint within token expiration time
            with freeze_time(base_time + timedelta(seconds=30)):
                access_response = c.post(
                    "/auth/check",
                    headers=[
                        (
                            "Authorization",
                            f"Bearer {login_response.json['access_token']}",
                        )
                    ],
                )
                self.assertEqual(access_response.status_code, 200)
                self.assertEqual(access_response.json["user_id"], self.user.id)

            # Refresh access token after expiration
            with freeze_time(
                base_time
                + timedelta(minutes=10 + app.config["ACCESS_TOKEN_EXPIRATION"])
            ):
                expired_access_response = c.post(
                    "/auth/check",
                    headers=[
                        (
                            "Authorization",
                            f"Bearer {login_response.json['access_token']}",
                        )
                    ],
                )
                self.assertEqual(expired_access_response.status_code, 401)

                refresh_response = c.post(
                    "/auth/refresh",
                    headers=[
                        (
                            "Authorization",
                            f"Bearer {login_response.json['refresh_token']}",
                        )
                    ],
                )
                self.assertEqual(refresh_response.status_code, 200)

                new_access_response = c.post(
                    "/auth/check",
                    headers=[
                        (
                            "Authorization",
                            f"Bearer {refresh_response.json['access_token']}",
                        )
                    ],
                )
                self.assertEqual(new_access_response.status_code, 200)
                self.assertEqual(
                    new_access_response.json["user_id"], self.user.id
                )

                reuse_refresh_token_response = c.post(
                    "/auth/refresh",
                    headers=[
                        (
                            "Authorization",
                            f"Bearer {login_response.json['refresh_token']}",
                        )
                    ],
                )
                self.assertEqual(reuse_refresh_token_response.status_code, 401)

    def test_access_fails_on_bad_token(self):
        base_time = datetime.now()
        with app.test_client() as c:
            # Step 1 : login
            with freeze_time(base_time):
                login_response = c.post(
                    "/auth/login",
                    json=dict(email=self.user.email, password="passwd"),
                )
                self.assertEqual(login_response.status_code, 200)

            with freeze_time(base_time + timedelta(seconds=30)):
                wrong_access_response = c.post(
                    "/auth/check",
                    headers=[
                        (
                            "Authorization",
                            f"Bearer {login_response.json['access_token']}abc",
                        )
                    ],
                )
                self.assertEqual(wrong_access_response.status_code, 401)

                mixing_tokens_response = c.post(
                    "/auth/check",
                    headers=[
                        (
                            "Authorization",
                            f"Bearer {login_response.json['refresh_token']}",
                        )
                    ],
                )
                self.assertEqual(mixing_tokens_response.status_code, 401)

    def test_refresh_fails_on_bad_token(self):
        with app.test_client() as c:
            login_response = c.post(
                "/auth/login",
                json=dict(email=self.user.email, password="passwd"),
            )
            self.assertEqual(login_response.status_code, 200)

            wrong_refresh_response = c.post(
                "/auth/refresh",
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response.json['refresh_token']}abc",
                    )
                ],
            )
            self.assertEqual(wrong_refresh_response.status_code, 401)

            mixing_tokens_response = c.post(
                "/auth/refresh",
                headers=[
                    (
                        "Authorization",
                        f"Bearer {login_response.json['access_token']}",
                    )
                ],
            )
            self.assertEqual(mixing_tokens_response.status_code, 401)

    def test_tokens_fail_on_revoked_user(self):
        base_time = datetime.now()
        with app.test_client() as c:
            # Step 1 : login
            with freeze_time(base_time):
                login_response = c.post(
                    "/auth/login",
                    json=dict(email=self.user.email, password="passwd"),
                )
                self.assertEqual(login_response.status_code, 200)

            # Revoke user
            self.user.refresh_token_nonce = None
            db.session.commit()

            with freeze_time(base_time + timedelta(seconds=30)):
                wrong_access_response = c.post(
                    "/auth/check",
                    headers=[
                        (
                            "Authorization",
                            f"Bearer {login_response.json['access_token']}",
                        )
                    ],
                )
                self.assertEqual(wrong_access_response.status_code, 401)

                wrong_refresh_response = c.post(
                    "/auth/refresh",
                    headers=[
                        (
                            "Authorization",
                            f"Bearer {login_response.json['refresh_token']}",
                        )
                    ],
                )
                self.assertEqual(wrong_refresh_response.status_code, 401)
