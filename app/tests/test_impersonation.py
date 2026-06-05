from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt as pyjwt

from app import app, db
from app.domain.totp import encrypt_secret, generate_totp_secret
from app.helpers.authentication import create_access_tokens_for
from app.helpers.errors import AuthorizationError
from app.helpers.mail_type import EmailType
from app.models.activity import Activity, ActivityType
from app.models.company import Company
from app.models.email import Email
from app.models.employment import Employment
from app.models.mission import Mission
from app.models.support_action_log import SupportActionLog
from app.models.team import Team
from app.models.totp_credential import TotpCredential
from app.models.user import User
from app.seed.factories import (
    CompanyFactory,
    EmploymentFactory,
    TeamFactory,
    UserFactory,
)
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


TEST_SCOPE_GUARD_ALLOWED_TABLES = frozenset(
    {
        "user",
        "employment",
        "company",
        "activity",
        "mission",
        "email",
        "team",
        "team_affiliation",
    }
)


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

        # JWT subject is the admin; target lives in impersonate_as claim
        decoded = pyjwt.decode(
            data["accessToken"],
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        self.assertEqual(decoded["identity"]["id"], self.admin.id)
        self.assertEqual(decoded["identity"]["impersonate_as"], self.target.id)

    def test_no_admin_token_cookie_on_start(self):
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
            self.assertFalse(
                admin_cookie_found,
                "admin_token cookie must not be used anymore",
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

    def test_self_impersonation_rejected(self):
        _enable_2fa(self.admin)
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=self.admin,
            variables={"userId": self.admin.id},
        )
        self.assertIsNotNone(response.json.get("errors"))

    def test_admin_target_rejected(self):
        other_admin = UserFactory.create(admin=True)
        db.session.commit()
        _enable_2fa(self.admin)
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=self.admin,
            variables={"userId": other_admin.id},
        )
        self.assertIsNotNone(response.json.get("errors"))


class TestStopImpersonation(BaseTest):
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

        # Start impersonation to get token
        start_resp = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=admin,
            variables={"userId": target.id},
        )
        imp_token = start_resp.json["data"]["account"]["startImpersonation"][
            "accessToken"
        ]

        # Stop impersonation — no admin_token cookie needed anymore
        with app.test_client() as c, app.app_context():
            resp = c.post(
                graphql_private_api_path,
                json=dict(query=STOP_IMPERSONATION),
                headers=[("Authorization", f"Bearer {imp_token}")],
            )
            data = resp.json["data"]["account"]["stopImpersonation"]
            self.assertTrue(data["success"])

            set_cookies = resp.headers.getlist("Set-Cookie")
            # Verify userId cookie is set to admin's ID
            user_id_cookie = [
                c for c in set_cookies if c.startswith("userId=")
            ]
            self.assertGreater(len(user_id_cookie), 0)
            self.assertIn(
                f"userId={admin.id}",
                user_id_cookie[0],
            )

            # Verify the new access token's identity matches the admin (no impersonate_as)
            access_cookie = [
                c
                for c in set_cookies
                if c.startswith(f"{app.config['JWT_ACCESS_COOKIE_NAME']}=")
            ][0]
            new_token = access_cookie.split(";", 1)[0].split("=", 1)[1]
            decoded = pyjwt.decode(
                new_token,
                app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )
            self.assertEqual(decoded["identity"]["id"], admin.id)
            self.assertNotIn("impersonate_as", decoded["identity"])


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
                "id": admin.id,
                "impersonate_as": target.id,
            },
            expires_delta=timedelta(seconds=-1),
        )

        check_resp = test_post_graphql(
            CHECK_AUTH,
            headers=[("Authorization", f"Bearer {expired_token}")],
        )
        self.assertIsNotNone(check_resp.json.get("errors"))

    def test_impersonation_session_survives_target_token_revocation(self):
        # JWT subject must be the admin so that target.latest_token_revocation_time
        # does not break the impersonation session (e.g. target resets password).
        from flask_jwt_extended import create_access_token

        admin = UserFactory.create(admin=True)
        target = UserFactory.create()
        db.session.commit()
        _enable_2fa(admin)

        imp_token = create_access_token(
            {"id": admin.id, "impersonate_as": target.id},
            expires_delta=timedelta(hours=2),
        )

        target.latest_token_revocation_time = datetime.now()
        db.session.commit()

        check_resp = test_post_graphql(
            CHECK_AUTH,
            headers=[("Authorization", f"Bearer {imp_token}")],
        )
        self.assertIsNone(check_resp.json.get("errors"))
        self.assertEqual(
            check_resp.json["data"]["checkAuth"]["userId"], target.id
        )


class TestImpersonationAuditListener(BaseTest):
    LISTENER_G = "app.helpers.impersonate_listener.g"

    def setUp(self):
        super().setUp()
        self.admin = UserFactory.create(admin=True)
        self.target = UserFactory.create()
        db.session.commit()

    def _impersonation_g(self):
        return SimpleNamespace(
            impersonate_by=self.admin.id,
            impersonated_user_id=self.target.id,
        )

    def test_insert_logged_during_impersonation(self):
        with patch(self.LISTENER_G, self._impersonation_g()):
            new_user = UserFactory.create()
            db.session.commit()

        logs = SupportActionLog.query.filter_by(
            support_user_id=self.admin.id,
            action="INSERT",
            table_name="user",
            row_id=new_user.id,
        ).all()
        self.assertEqual(len(logs), 1)
        self.assertIsNotNone(logs[0].new_values)
        self.assertIsNone(logs[0].old_values)
        self.assertEqual(logs[0].impersonated_user_id, self.target.id)

    def test_update_logged_during_impersonation(self):
        with patch(self.LISTENER_G, self._impersonation_g()):
            self.target.email = "updated@test.com"
            db.session.commit()

        logs = SupportActionLog.query.filter_by(
            support_user_id=self.admin.id,
            action="UPDATE",
            table_name="user",
            row_id=self.target.id,
        ).all()
        self.assertEqual(len(logs), 1)
        self.assertIsNotNone(logs[0].old_values)
        self.assertIn("email", logs[0].old_values)
        self.assertIsNotNone(logs[0].new_values)
        self.assertEqual(logs[0].new_values["email"], "updated@test.com")
        # new_values should only contain changed columns
        self.assertNotIn("first_name", logs[0].new_values)

    def test_delete_logged_during_impersonation(self):
        other_user = UserFactory.create()
        db.session.commit()
        other_user_id = other_user.id

        with patch(self.LISTENER_G, self._impersonation_g()):
            db.session.delete(other_user)
            db.session.commit()

        logs = SupportActionLog.query.filter_by(
            support_user_id=self.admin.id,
            action="DELETE",
            table_name="user",
            row_id=other_user_id,
        ).all()
        self.assertEqual(len(logs), 1)
        self.assertIsNotNone(logs[0].old_values)
        self.assertIsNone(logs[0].new_values)

    def test_no_log_without_impersonation(self):
        new_user = UserFactory.create()
        db.session.commit()

        logs = SupportActionLog.query.all()
        self.assertEqual(len(logs), 0)

    def test_no_recursive_log_on_support_action_log(self):
        with patch(self.LISTENER_G, self._impersonation_g()):
            log = SupportActionLog(
                support_user_id=self.admin.id,
                impersonated_user_id=self.target.id,
                table_name="user",
                row_id=1,
                action="UPDATE",
            )
            db.session.add(log)
            db.session.commit()

        all_logs = SupportActionLog.query.all()
        self.assertEqual(len(all_logs), 1)

    def test_sensitive_columns_excluded_from_audit_log(self):
        with patch(self.LISTENER_G, self._impersonation_g()):
            new_user = UserFactory.create()
            db.session.commit()

        logs = SupportActionLog.query.filter_by(
            support_user_id=self.admin.id,
            action="INSERT",
            table_name="user",
            row_id=new_user.id,
        ).all()
        self.assertEqual(len(logs), 1)
        new_values = logs[0].new_values
        # Sensitive columns must be excluded
        for key in (
            "password",
            "ssn",
            "activation_email_token",
            "france_connect_id",
            "france_connect_info",
        ):
            self.assertNotIn(key, new_values)
        # Non-sensitive columns should be present
        self.assertIn("email", new_values)
        self.assertIn("first_name", new_values)

    def test_listener_registered_on_session(self):
        from sqlalchemy import event

        from app.helpers.impersonate_listener import (
            log_impersonation_actions,
        )

        self.assertTrue(
            event.contains(
                db.session,
                "after_flush",
                log_impersonation_actions,
            ),
            "after_flush audit listener must be registered",
        )

    def test_ignored_tables_not_logged(self):
        """Tables in AUDIT_IGNORED_TABLES must not be logged."""
        from app.helpers.impersonate_listener import (
            AUDIT_IGNORED_TABLES,
        )

        self.assertIn("user_agreement", AUDIT_IGNORED_TABLES)

        from app.models.user_agreement import UserAgreement

        with patch(self.LISTENER_G, self._impersonation_g()):
            agreement = UserAgreement(
                user_id=self.target.id,
                status="pending",
                cgu_version="v1.0",
            )
            db.session.add(agreement)
            db.session.commit()

        logs = SupportActionLog.query.filter_by(
            table_name="user_agreement",
        ).all()
        self.assertEqual(len(logs), 0)

    def test_empty_update_not_logged(self):
        """Guard functions return None on unmodified object,
        preventing spurious audit entries."""
        from app.helpers.impersonate_listener import (
            _get_old_values,
            _get_changed_new_values,
        )

        # Verify guard functions return None for unmodified obj
        self.assertIsNone(_get_old_values(self.target))
        self.assertIsNone(_get_changed_new_values(self.target))

        with patch(self.LISTENER_G, self._impersonation_g()):
            db.session.commit()

        logs = SupportActionLog.query.filter_by(
            action="UPDATE",
            table_name="user",
            row_id=self.target.id,
        ).all()
        self.assertEqual(len(logs), 0)

    def test_token_in_redacted_columns(self):
        from app.helpers.impersonate_listener import (
            REDACTED_COLUMNS,
        )

        self.assertIn("token", REDACTED_COLUMNS)


class TestImpersonationScopeGuard(BaseTest):
    LISTENER_G = "app.helpers.impersonate_listener.g"

    def setUp(self):
        super().setUp()
        self.admin = UserFactory.create(admin=True)
        self.target = UserFactory.create()
        db.session.commit()
        self._orig_guard = app.config.get("IMPERSONATION_ALLOWED_TABLES")

    def tearDown(self):
        app.config["IMPERSONATION_ALLOWED_TABLES"] = self._orig_guard
        super().tearDown()

    def _impersonation_g(self):
        return SimpleNamespace(
            impersonate_by=self.admin.id,
            impersonated_user_id=self.target.id,
        )

    def test_guard_enabled_allowed_table_passes(self):
        with patch(self.LISTENER_G, self._impersonation_g()):
            app.config["IMPERSONATION_ALLOWED_TABLES"] = (
                TEST_SCOPE_GUARD_ALLOWED_TABLES
            )
            self.target.email = "guard-allowed@test.com"
            db.session.commit()

        self.assertEqual(
            User.query.get(self.target.id).email,
            "guard-allowed@test.com",
        )

    def test_guard_enabled_disallowed_insert_raises(self):
        with patch(self.LISTENER_G, self._impersonation_g()):
            app.config["IMPERSONATION_ALLOWED_TABLES"] = (
                TEST_SCOPE_GUARD_ALLOWED_TABLES
            )
            cred = TotpCredential(
                owner_type="user",
                owner_id=self.target.id,
                secret="fake-secret",
                enabled=False,
            )
            db.session.add(cred)
            with self.assertRaises(AuthorizationError) as ctx:
                db.session.flush()
            self.assertIn("totp_credential", str(ctx.exception))
            db.session.rollback()

    def test_guard_enabled_disallowed_update_raises(self):
        cred = TotpCredential(
            owner_type="user",
            owner_id=self.target.id,
            secret="fake-secret",
            enabled=False,
        )
        db.session.add(cred)
        db.session.commit()

        with patch(self.LISTENER_G, self._impersonation_g()):
            app.config["IMPERSONATION_ALLOWED_TABLES"] = (
                TEST_SCOPE_GUARD_ALLOWED_TABLES
            )
            cred.enabled = True
            with self.assertRaises(AuthorizationError) as ctx:
                db.session.flush()
            self.assertIn("totp_credential", str(ctx.exception))
            db.session.rollback()

    def test_guard_disabled_all_passes(self):
        with patch(self.LISTENER_G, self._impersonation_g()):
            app.config["IMPERSONATION_ALLOWED_TABLES"] = frozenset()
            cred = TotpCredential(
                owner_type="user",
                owner_id=self.target.id,
                secret="fake-secret",
                enabled=False,
            )
            db.session.add(cred)
            db.session.commit()

        self.assertEqual(TotpCredential.query.count(), 1)

    def test_guard_listener_registered_on_session(self):
        from sqlalchemy import event

        from app.helpers.impersonate_listener import (
            guard_impersonation_scope,
        )

        self.assertTrue(
            event.contains(
                db.session,
                "before_flush",
                guard_impersonation_scope,
            ),
            "scope guard listener must be registered",
        )


SEARCH_USERS_QUERY = """
    query ($search: String!, $offset: Int) {
        searchUsersForImpersonation(search: $search, offset: $offset) {
            results {
                id
                email
                firstName
                lastName
                companies { name siren }
            }
            hasMore
        }
    }
"""


class TestSearchUsersForImpersonation(BaseTest):
    def setUp(self):
        super().setUp()
        self.admin = UserFactory.create(
            admin=True,
            email="admin@mobilic.test",
            first_name="Kelly",
            last_name="Support",
        )
        _enable_2fa(self.admin)
        self.target = UserFactory.create(
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
        )
        self.company = CompanyFactory.create(
            usual_name="Transport Express",
            siren="123456789",
        )
        EmploymentFactory.create(
            user=self.target,
            company=self.company,
        )
        db.session.commit()

    def test_search_by_email(self):
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=self.admin,
            variables={"search": "john.doe"},
        )
        data = response.json
        self.assertNotIn("errors", data)
        results = data["data"]["searchUsersForImpersonation"]["results"]
        self.assertGreaterEqual(len(results), 1)
        emails = [r["email"] for r in results]
        self.assertIn("john.doe@example.com", emails)

    def test_search_by_name(self):
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=self.admin,
            variables={"search": "Doe"},
        )
        data = response.json
        self.assertNotIn("errors", data)
        results = data["data"]["searchUsersForImpersonation"]["results"]
        self.assertGreaterEqual(len(results), 1)
        names = [r["lastName"] for r in results]
        self.assertIn("Doe", names)

    def test_search_by_siren(self):
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=self.admin,
            variables={"search": "123456789"},
        )
        data = response.json
        self.assertNotIn("errors", data)
        results = data["data"]["searchUsersForImpersonation"]["results"]
        self.assertGreaterEqual(len(results), 1)
        ids = [r["id"] for r in results]
        self.assertIn(self.target.id, ids)

    def test_search_requires_admin(self):
        regular_user = UserFactory.create(admin=False)
        db.session.commit()
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=regular_user,
            variables={"search": "john"},
        )
        data = response.json
        self.assertIn("errors", data)

    def test_search_min_3_chars(self):
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=self.admin,
            variables={"search": "ab"},
        )
        data = response.json
        self.assertNotIn("errors", data)
        results = data["data"]["searchUsersForImpersonation"]["results"]
        self.assertEqual(len(results), 0)

    def test_search_requires_2fa(self):
        admin_no_2fa = UserFactory.create(
            admin=True,
            email="admin-no2fa@mobilic.test",
        )
        db.session.commit()
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=admin_no_2fa,
            variables={"search": "john"},
        )
        data = response.json
        self.assertIn("errors", data)

    def test_search_special_characters_escaped(self):
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=self.admin,
            variables={"search": "%_%"},
        )
        data = response.json
        self.assertNotIn("errors", data)
        results = data["data"]["searchUsersForImpersonation"]["results"]
        self.assertEqual(len(results), 0)

    def test_search_results_limited_to_20_with_has_more(self):
        for i in range(25):
            user = UserFactory.create(
                email=f"bulkuser{i}@test.com",
                first_name="BulkTest",
                last_name=f"User{i}",
            )
            EmploymentFactory.create(
                user=user,
                company=self.company,
            )
        db.session.commit()
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=self.admin,
            variables={"search": "BulkTest"},
        )
        data = response.json
        self.assertNotIn("errors", data)
        page = data["data"]["searchUsersForImpersonation"]
        self.assertEqual(len(page["results"]), 20)
        self.assertTrue(page["hasMore"])

    def test_search_pagination_offset(self):
        for i in range(25):
            user = UserFactory.create(
                email=f"bulkuser{i}@test.com",
                first_name="BulkTest",
                last_name=f"User{i}",
            )
            EmploymentFactory.create(
                user=user,
                company=self.company,
            )
        db.session.commit()
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=self.admin,
            variables={"search": "BulkTest", "offset": 20},
        )
        data = response.json
        self.assertNotIn("errors", data)
        page = data["data"]["searchUsersForImpersonation"]
        self.assertEqual(len(page["results"]), 5)
        self.assertFalse(page["hasMore"])


class TestSecurityEndToEnd(BaseTest):
    """Task 13: IDOR and cross-cutting security tests."""

    LISTENER_G = "app.helpers.impersonate_listener.g"

    def setUp(self):
        super().setUp()
        self.admin = UserFactory.create(admin=True)
        self.target = UserFactory.create(
            email="target-e2e@test.com",
            first_name="Target",
            last_name="User",
        )
        self.company = CompanyFactory.create(
            usual_name="E2E Corp",
            siren="111222333",
        )
        self.employment = EmploymentFactory.create(
            user=self.target,
            company=self.company,
            has_admin_rights=False,
        )
        self.team = TeamFactory.create(
            name="E2E Team",
            company=self.company,
        )
        db.session.commit()
        _enable_2fa(self.admin)
        self._orig_guard = app.config.get("IMPERSONATION_ALLOWED_TABLES")

    def tearDown(self):
        app.config["IMPERSONATION_ALLOWED_TABLES"] = self._orig_guard
        super().tearDown()

    def _impersonation_g(self):
        return SimpleNamespace(
            impersonate_by=self.admin.id,
            impersonated_user_id=self.target.id,
        )

    # --- 13.1 Non-admin IDOR ---

    def test_non_admin_cannot_start_impersonation(self):
        non_admin = UserFactory.create(admin=False)
        db.session.commit()
        _enable_2fa(non_admin)
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=non_admin,
            variables={"userId": self.target.id},
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertEqual(
            errors[0]["extensions"]["code"],
            "AUTHORIZATION_ERROR",
        )

    def test_non_admin_cannot_search_users(self):
        non_admin = UserFactory.create(admin=False)
        db.session.commit()
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=non_admin,
            variables={"search": "target"},
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertEqual(
            errors[0]["extensions"]["code"],
            "AUTHORIZATION_ERROR",
        )

    # --- 13.2 Admin without 2FA ---

    def test_admin_without_2fa_cannot_impersonate(self):
        admin_no_2fa = UserFactory.create(admin=True)
        db.session.commit()
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=admin_no_2fa,
            variables={"userId": self.target.id},
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertEqual(
            errors[0]["extensions"]["code"],
            "AUTHORIZATION_ERROR",
        )

    def test_admin_without_2fa_cannot_search_users(self):
        admin_no_2fa = UserFactory.create(admin=True)
        db.session.commit()
        response = test_post_graphql_unexposed(
            SEARCH_USERS_QUERY,
            mock_authentication_with_user=admin_no_2fa,
            variables={"search": "target"},
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertEqual(
            errors[0]["extensions"]["code"],
            "AUTHORIZATION_ERROR",
        )

    # --- 13.3 JWT expiration ---

    def test_impersonation_jwt_has_2h_expiration(self):
        response = test_post_graphql_unexposed(
            START_IMPERSONATION,
            mock_authentication_with_user=self.admin,
            variables={"userId": self.target.id},
        )
        token = response.json["data"]["account"]["startImpersonation"][
            "accessToken"
        ]
        decoded = pyjwt.decode(
            token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        ttl = decoded["exp"] - decoded["iat"]
        # 2h = 7200s, with 60s tolerance
        self.assertGreaterEqual(ttl, 7200 - 60)
        self.assertLessEqual(ttl, 7200 + 60)

    # --- 13.4 Whitelist exhaustivity ---

    def test_whitelist_change_user_email(self):
        """Support user changes email — table `user`."""
        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            self.target.email = "kelly-changed@test.com"
            db.session.commit()
        self.assertEqual(
            User.query.get(self.target.id).email,
            "kelly-changed@test.com",
        )
        logs = SupportActionLog.query.filter_by(
            table_name="user",
            action="UPDATE",
            row_id=self.target.id,
        ).all()
        self.assertEqual(len(logs), 1)
        self.assertIn("email", logs[0].new_values)

    def test_whitelist_change_admin_rights(self):
        """Support user changes admin rights — table `employment`."""
        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            self.employment.has_admin_rights = True
            db.session.commit()
        fetched = Employment.query.get(self.employment.id)
        self.assertTrue(fetched.has_admin_rights)
        logs = SupportActionLog.query.filter_by(
            table_name="employment",
            action="UPDATE",
        ).all()
        self.assertEqual(len(logs), 1)

    def test_whitelist_terminate_employment(self):
        """Support user terminates employment — table `employment`."""
        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            self.employment.end_date = date.today()
            db.session.commit()
        fetched = Employment.query.get(self.employment.id)
        self.assertEqual(fetched.end_date, date.today())
        logs = SupportActionLog.query.filter_by(
            table_name="employment",
            action="UPDATE",
            row_id=self.employment.id,
        ).all()
        self.assertEqual(len(logs), 1)

    def test_whitelist_modify_company_settings(self):
        """Support user modifies company settings — table `company`."""
        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            self.company.require_mission_name = False
            db.session.commit()
        fetched = Company.query.get(self.company.id)
        self.assertFalse(fetched.require_mission_name)
        logs = SupportActionLog.query.filter_by(
            table_name="company",
            action="UPDATE",
            row_id=self.company.id,
        ).all()
        self.assertEqual(len(logs), 1)

    def test_whitelist_end_activity(self):
        """Support user stops ongoing activity — table `activity`."""
        now = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
        start = now - timedelta(hours=1)
        mission = Mission(
            company_id=self.company.id,
            reception_time=start,
            submitter_id=self.target.id,
        )
        db.session.add(mission)
        db.session.flush()
        activity = Activity(
            mission_id=mission.id,
            user_id=self.target.id,
            submitter_id=self.target.id,
            reception_time=start,
            start_time=start,
            end_time=None,
            type=ActivityType.DRIVE,
            last_update_time=start,
        )
        db.session.add(activity)
        db.session.commit()

        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            activity.end_time = now
            activity.last_update_time = now
            db.session.commit()
        fetched = Activity.query.get(activity.id)
        self.assertEqual(fetched.end_time, now)
        logs = SupportActionLog.query.filter_by(
            table_name="activity",
            action="UPDATE",
            row_id=activity.id,
        ).all()
        self.assertEqual(len(logs), 1)

    def test_whitelist_modify_team(self):
        """Support user renames team — table `team`."""
        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            self.team.name = "Renamed Team"
            db.session.commit()
        fetched = Team.query.get(self.team.id)
        self.assertEqual(fetched.name, "Renamed Team")
        logs = SupportActionLog.query.filter_by(
            table_name="team",
            action="UPDATE",
            row_id=self.team.id,
        ).all()
        self.assertEqual(len(logs), 1)

    def test_whitelist_modify_mission_name(self):
        """Support user renames mission — table `mission`."""
        mission = Mission(
            company_id=self.company.id,
            reception_time=datetime.now(tz=timezone.utc),
            submitter_id=self.target.id,
            name="Original",
        )
        db.session.add(mission)
        db.session.commit()

        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            mission.name = "Support Renamed"
            db.session.commit()
        fetched = Mission.query.get(mission.id)
        self.assertEqual(fetched.name, "Support Renamed")
        logs = SupportActionLog.query.filter_by(
            table_name="mission",
            action="UPDATE",
            row_id=mission.id,
        ).all()
        self.assertEqual(len(logs), 1)

    def test_whitelist_insert_email(self):
        """Support user triggers email send — table `email`."""
        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            email = Email(
                mailjet_id="test-whitelist-email",
                address="kelly-email@test.com",
                type=EmailType.INVITATION,
                user_id=self.target.id,
            )
            db.session.add(email)
            db.session.commit()
        logs = SupportActionLog.query.filter_by(
            table_name="email",
            action="INSERT",
        ).all()
        self.assertEqual(len(logs), 1)

    def test_whitelist_delete_employment(self):
        """Support user deletes employment — DELETE on `employment`."""
        other_company = CompanyFactory.create(
            usual_name="Delete Corp",
            siren="999888777",
        )
        extra_emp = EmploymentFactory.create(
            user=self.target,
            company=other_company,
        )
        db.session.commit()
        emp_id = extra_emp.id

        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            db.session.delete(extra_emp)
            db.session.commit()
        self.assertIsNone(Employment.query.get(emp_id))
        logs = SupportActionLog.query.filter_by(
            table_name="employment",
            action="DELETE",
            row_id=emp_id,
        ).all()
        self.assertEqual(len(logs), 1)

    def test_expired_impersonation_token_rejected(self):
        from flask_jwt_extended import create_access_token

        expired_token = create_access_token(
            {
                "id": self.admin.id,
                "impersonate_as": self.target.id,
            },
            expires_delta=timedelta(seconds=-1),
        )
        check_resp = test_post_graphql(
            CHECK_AUTH,
            headers=[("Authorization", f"Bearer {expired_token}")],
        )
        self.assertIsNotNone(check_resp.json.get("errors"))

    def test_self_impersonation_still_audited(self):
        """Self-impersonation (edge case) still generates audit logs."""
        with patch(
            self.LISTENER_G,
            SimpleNamespace(
                impersonate_by=self.admin.id,
                impersonated_user_id=self.admin.id,
            ),
        ):
            self.admin.first_name = "SelfTest"
            db.session.commit()
        logs = SupportActionLog.query.filter_by(
            support_user_id=self.admin.id,
            impersonated_user_id=self.admin.id,
        ).all()
        self.assertEqual(len(logs), 1)

    def test_all_kelly_tables_covered_by_whitelist(self):
        """Meta-test: run all support user actions, collect touched tables,
        verify all are in scope guard whitelist."""

        now = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
        start = now - timedelta(hours=1)
        mission = Mission(
            company_id=self.company.id,
            reception_time=start,
            submitter_id=self.target.id,
        )
        db.session.add(mission)
        db.session.flush()
        activity = Activity(
            mission_id=mission.id,
            user_id=self.target.id,
            submitter_id=self.target.id,
            reception_time=start,
            start_time=start,
            end_time=None,
            type=ActivityType.DRIVE,
            last_update_time=start,
        )
        db.session.add(activity)
        db.session.commit()

        app.config["IMPERSONATION_ALLOWED_TABLES"] = (
            TEST_SCOPE_GUARD_ALLOWED_TABLES
        )
        with patch(self.LISTENER_G, self._impersonation_g()):
            # Change email (user)
            self.target.email = "meta-kelly@test.com"
            db.session.commit()
            # Change admin rights (employment)
            self.employment.has_admin_rights = True
            db.session.commit()
            # Modify company (company)
            self.company.require_mission_name = True
            db.session.commit()
            # Modify team (team)
            self.team.name = "Meta Team"
            db.session.commit()
            # End activity (activity)
            activity.end_time = now
            activity.last_update_time = now
            db.session.commit()
            # Modify mission (mission)
            mission.name = "Meta Mission"
            db.session.commit()
            # Send email (email)
            email = Email(
                mailjet_id="meta-test-email",
                address="meta@test.com",
                type=EmailType.INVITATION,
                user_id=self.target.id,
            )
            db.session.add(email)
            db.session.commit()

        tables_touched = {
            log.table_name for log in SupportActionLog.query.all()
        }
        self.assertGreater(len(tables_touched), 0)
        for table in tables_touched:
            self.assertIn(
                table,
                TEST_SCOPE_GUARD_ALLOWED_TABLES,
                f"Table '{table}' touched during impersonation "
                f"but NOT in whitelist",
            )


class TestPurgeSupportActionLogs(BaseTest):
    def setUp(self):
        super().setUp()
        self.admin = UserFactory.create(admin=True)
        self.target = UserFactory.create()
        db.session.commit()

    def _create_log(self, age_months=0):
        now = datetime.now(tz=timezone.utc)
        log = SupportActionLog(
            support_user_id=self.admin.id,
            impersonated_user_id=self.target.id,
            table_name="user",
            row_id=self.target.id,
            action="UPDATE",
            old_values={"email": "old@test.com"},
            new_values={"email": "new@test.com"},
        )
        db.session.add(log)
        db.session.commit()
        if age_months > 0:
            old_date = now - timedelta(days=30 * age_months + 1)
            db.session.execute(
                db.text(
                    "UPDATE support_action_log "
                    "SET creation_time = :d WHERE id = :id"
                ),
                {"d": old_date, "id": log.id},
            )
            db.session.commit()
        return log

    def test_purge_deletes_old_entries(self):
        from app.services.anonymization.purge_support_action_logs import (
            purge_expired_support_action_logs,
        )

        old_log_id = self._create_log(age_months=4).id
        recent_log_id = self._create_log(age_months=0).id

        deleted = purge_expired_support_action_logs()
        self.assertEqual(deleted, 1)
        db.session.expire_all()
        self.assertIsNone(SupportActionLog.query.get(old_log_id))
        self.assertIsNotNone(SupportActionLog.query.get(recent_log_id))

    def test_purge_preserves_recent_entries(self):
        from app.services.anonymization.purge_support_action_logs import (
            purge_expired_support_action_logs,
        )

        self._create_log(age_months=0)
        self._create_log(age_months=2)

        deleted = purge_expired_support_action_logs()
        self.assertEqual(deleted, 0)
        self.assertEqual(SupportActionLog.query.count(), 2)
