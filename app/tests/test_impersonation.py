from datetime import timedelta

from app.helpers.errors import AuthorizationError

import jwt as pyjwt

from app import app, db
from app.domain.totp import encrypt_secret, generate_totp_secret
from app.helpers.authentication import create_access_tokens_for
from app.models.support_action_log import SupportActionLog
from app.models.totp_credential import TotpCredential
from app.seed.factories import UserFactory
from app.tests import (
    BaseTest,
    graphql_private_api_path,
    test_post_graphql,
    test_post_graphql_unexposed,
)


START_IMPERSONATION = """
    mutation ($userId: Int!) {
        account {
            startImpersonation(userId: $userId) {
                accessToken
                impersonatedUserId
            }
        }
    }
"""

STOP_IMPERSONATION = """
    mutation {
        account {
            stopImpersonation {
                success
            }
        }
    }
"""

CHECK_AUTH = """
    query { checkAuth { success userId } }
"""


def _enable_2fa(user):
    secret = generate_totp_secret()
    cred = TotpCredential(
        owner_type="user",
        owner_id=user.id,
        secret=encrypt_secret(secret),
        enabled=True,
    )
    db.session.add(cred)
    db.session.commit()
    return secret


class TestSupportActionLogModel(BaseTest):
    def test_create_support_action_log(self):
        admin = UserFactory.create(admin=True)
        target = UserFactory.create()
        db.session.commit()

        log = SupportActionLog(
            support_user_id=admin.id,
            impersonated_user_id=target.id,
            table_name="user",
            row_id=target.id,
            action="UPDATE",
            old_values={"email": "old@test.com"},
            new_values={"email": "new@test.com"},
        )
        db.session.add(log)
        db.session.commit()

        fetched = SupportActionLog.query.filter_by(
            support_user_id=admin.id
        ).one()
        self.assertEqual(fetched.table_name, "user")
        self.assertEqual(fetched.action, "UPDATE")
        self.assertIsNotNone(fetched.creation_time)

    def test_insert_action_log(self):
        admin = UserFactory.create(admin=True)
        target = UserFactory.create()
        db.session.commit()

        log = SupportActionLog(
            support_user_id=admin.id,
            impersonated_user_id=target.id,
            table_name="employment",
            row_id=999,
            action="INSERT",
            old_values=None,
            new_values={"user_id": target.id},
        )
        db.session.add(log)
        db.session.commit()

        fetched = SupportActionLog.query.get(log.id)
        self.assertEqual(fetched.action, "INSERT")
        self.assertIsNone(fetched.old_values)

    def test_query_by_support_user(self):
        admin = UserFactory.create(admin=True)
        target1 = UserFactory.create()
        target2 = UserFactory.create()
        db.session.commit()

        for target in [target1, target2]:
            db.session.add(
                SupportActionLog(
                    support_user_id=admin.id,
                    impersonated_user_id=target.id,
                    table_name="user",
                    row_id=target.id,
                    action="UPDATE",
                )
            )
        db.session.commit()

        logs = SupportActionLog.query.filter_by(support_user_id=admin.id).all()
        self.assertEqual(len(logs), 2)


class TestStartImpersonation(BaseTest):
    def setUp(self):
        super().setUp()
        self.admin = UserFactory.create(admin=True)
        self.target = UserFactory.create()
        db.session.commit()

    def test_admin_with_2fa_can_impersonate(self):
        _enable_2fa(self.admin)
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=self.admin,
            variables={"userId": self.target.id},
        )
        data = response.json["data"]["account"]["startImpersonation"]
        self.assertIsNotNone(data["accessToken"])
        self.assertEqual(data["impersonatedUserId"], self.target.id)

        # Verify JWT contains impersonate_by claim
        decoded = pyjwt.decode(
            data["accessToken"],
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        self.assertEqual(decoded["identity"]["impersonate_by"], self.admin.id)
        self.assertEqual(decoded["identity"]["id"], self.target.id)

    def test_admin_token_cookie_set_on_start(self):
        _enable_2fa(self.admin)
        admin_tokens = create_access_tokens_for(self.admin)

        with app.test_client() as c, app.app_context():
            c.set_cookie(
                app.config["JWT_ACCESS_COOKIE_NAME"],
                admin_tokens["access_token"],
            )
            resp = c.post(
                graphql_private_api_path,
                json=dict(
                    query=START_IMPERSONATION,
                    variables={"userId": self.target.id},
                ),
            )
            self.assertIsNone(resp.json.get("errors"))
            set_cookie_headers = resp.headers.getlist("Set-Cookie")
            admin_cookie_found = any(
                "admin_token=" in c for c in set_cookie_headers
            )
            self.assertTrue(
                admin_cookie_found,
                "admin_token cookie must be set after start",
            )

    def test_non_admin_rejected(self):
        non_admin = UserFactory.create(admin=False)
        db.session.commit()
        _enable_2fa(non_admin)
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=non_admin,
            variables={"userId": self.target.id},
        )
        self.assertIsNotNone(response.json.get("errors"))

    def test_admin_without_2fa_rejected(self):
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=self.admin,
            variables={"userId": self.target.id},
        )
        self.assertIsNotNone(response.json.get("errors"))

    def test_impersonation_token_works_as_auth(self):
        _enable_2fa(self.admin)
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=self.admin,
            variables={"userId": self.target.id},
        )
        token = response.json["data"]["account"]["startImpersonation"][
            "accessToken"
        ]

        # Use impersonation token to query as target user
        check_response = test_post_graphql(
            CHECK_AUTH,
            headers=[("Authorization", f"Bearer {token}")],
        )
        data = check_response.json["data"]["checkAuth"]
        self.assertTrue(data["success"])
        self.assertEqual(data["userId"], self.target.id)

    def test_invalid_target_user_rejected(self):
        _enable_2fa(self.admin)
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=self.admin,
            variables={"userId": 999999},
        )
        self.assertIsNotNone(response.json.get("errors"))


class TestStopImpersonation(BaseTest):
    def test_stop_without_admin_cookie_fails(self):
        admin = UserFactory.create(admin=True)
        target = UserFactory.create()
        db.session.commit()
        _enable_2fa(admin)

        # Get impersonation token (so g.impersonate_by is set)
        start_resp = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=admin,
            variables={"userId": target.id},
        )
        imp_token = start_resp.json["data"]["account"]["startImpersonation"][
            "accessToken"
        ]

        # Call stop with impersonation JWT but no admin_token cookie
        with app.test_client() as c, app.app_context():
            resp = c.post(
                graphql_private_api_path,
                json=dict(query=STOP_IMPERSONATION),
                headers=[("Authorization", f"Bearer {imp_token}")],
            )
            self.assertIsNotNone(resp.json.get("errors"))

    def test_stop_without_impersonation_session_fails(self):
        admin = UserFactory.create(admin=True)
        db.session.commit()

        # Normal auth (not impersonating) — should be rejected
        response = test_post_graphql_unexposed(
            STOP_IMPERSONATION,
            mock_authentication_with_user=admin,
        )
        self.assertIsNotNone(response.json.get("errors"))

    def test_stop_restores_admin_session(self):
        admin = UserFactory.create(admin=True)
        target = UserFactory.create()
        db.session.commit()
        _enable_2fa(admin)

        # Create admin access token
        admin_tokens = create_access_tokens_for(admin)
        admin_access_token = admin_tokens["access_token"]

        # Start impersonation to get token
        start_resp = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=admin,
            variables={"userId": target.id},
        )
        imp_token = start_resp.json["data"]["account"]["startImpersonation"][
            "accessToken"
        ]

        # Stop impersonation with valid admin_token cookie
        with app.test_client() as c, app.app_context():
            c.set_cookie("admin_token", admin_access_token)
            resp = c.post(
                graphql_private_api_path,
                json=dict(query=STOP_IMPERSONATION),
                headers=[("Authorization", f"Bearer {imp_token}")],
            )
            data = resp.json["data"]["account"]["stopImpersonation"]
            self.assertTrue(data["success"])

            # Verify admin_token cookie is deleted
            set_cookies = resp.headers.getlist("Set-Cookie")
            admin_token_deleted = any(
                "admin_token=" in c
                and ("Max-Age=0" in c or "expires=" in c.lower())
                for c in set_cookies
            )
            self.assertTrue(
                admin_token_deleted,
                "admin_token cookie must be deleted after stop",
            )

            # Verify userId cookie is set to admin's ID
            user_id_cookie = [
                c for c in set_cookies if c.startswith("userId=")
            ]
            self.assertTrue(len(user_id_cookie) > 0)
            self.assertIn(
                f"userId={admin.id}",
                user_id_cookie[0],
            )


class TestImpersonationMiddleware(BaseTest):
    def test_impersonate_by_set_in_g(self):
        admin = UserFactory.create(admin=True)
        target = UserFactory.create()
        db.session.commit()
        _enable_2fa(admin)

        # Start impersonation to get token
        start_resp = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=admin,
            variables={"userId": target.id},
        )
        token = start_resp.json["data"]["account"]["startImpersonation"][
            "accessToken"
        ]

        # Use impersonation token — middleware should set
        # g.impersonate_by
        check_resp = test_post_graphql(
            CHECK_AUTH,
            headers=[("Authorization", f"Bearer {token}")],
        )
        data = check_resp.json["data"]["checkAuth"]
        self.assertEqual(data["userId"], target.id)

    def test_expired_impersonation_token_rejected(self):
        from flask_jwt_extended import create_access_token

        admin = UserFactory.create(admin=True)
        target = UserFactory.create()
        db.session.commit()

        # Create an already-expired impersonation token
        expired_token = create_access_token(
            {
                "id": target.id,
                "impersonate_by": admin.id,
            },
            expires_delta=timedelta(seconds=-1),
        )

        check_resp = test_post_graphql(
            CHECK_AUTH,
            headers=[("Authorization", f"Bearer {expired_token}")],
        )
        self.assertIsNotNone(check_resp.json.get("errors"))
