from datetime import datetime, timedelta
from flask_jwt_extended import decode_token
from freezegun import freeze_time

from app import app, db
from app.models.controller_refresh_token import ControllerRefreshToken
from app.models.refresh_token import RefreshToken
from app.seed import ControllerUserFactory, UserFactory
from app.tests import BaseTest, test_post_graphql
from app.tests.helpers import ApiRequests

REFRESH_QUERY = """
    mutation {
        auth {
            refresh {
                accessToken
                refreshToken
            }
        }
    }
"""


class TestRefreshTokenRotation(BaseTest):
    def setUp(self):
        super().setUp()
        self.user = UserFactory.create(password="passwd")

    def _login(self):
        response = test_post_graphql(
            ApiRequests.login_query,
            variables=dict(email=self.user.email, password="passwd"),
        )
        return response.json["data"]["auth"]["login"]

    def _refresh(self, refresh_jwt):
        return test_post_graphql(
            REFRESH_QUERY,
            headers=[("Authorization", f"Bearer {refresh_jwt}")],
        )

    def _user_tokens(self, consumed=None):
        query = RefreshToken.query.filter_by(user_id=self.user.id)
        if consumed is True:
            query = query.filter(RefreshToken.consumed_at.isnot(None))
        elif consumed is False:
            query = query.filter(RefreshToken.consumed_at.is_(None))
        return query.all()

    def test_expired_refresh_token_is_rejected(self):
        base_time = datetime.now()
        with freeze_time(base_time):
            login_data = self._login()

        with freeze_time(
            base_time
            + app.config["REFRESH_TOKEN_EXPIRATION"]
            + timedelta(days=1)
        ):
            response = self._refresh(login_data["refreshToken"])
            self.assertIsNotNone(response.json.get("errors"))

    def test_cap_only_counts_live_tokens(self):
        base_time = datetime.now()
        with freeze_time(base_time):
            login_data = self._login()
            refresh_response = self._refresh(login_data["refreshToken"])
            self.assertIsNone(refresh_response.json.get("errors"))
            self.assertEqual(1, len(self._user_tokens(consumed=True)))

            for _ in range(6):
                self._login()

        self.assertEqual(5, len(self._user_tokens(consumed=False)))
        # the consumed predecessor is kept for the grace period, the cap
        # only evicts live tokens
        self.assertEqual(1, len(self._user_tokens(consumed=True)))

    def test_purge_deletes_expired_and_old_consumed_tokens(self):
        login_1 = self._login()
        login_2 = self._login()
        self._refresh(login_2["refreshToken"])
        self._login()

        # Age the rows directly : freeze_time cannot patch the
        # creation_time column default captured by SQLAlchemy at import
        idle_token_string = decode_token(login_1["refreshToken"])["identity"][
            "token"
        ]
        RefreshToken.query.filter_by(token=idle_token_string).update(
            {"creation_time": datetime.now() - timedelta(days=100)}
        )
        RefreshToken.query.filter(RefreshToken.consumed_at.isnot(None)).update(
            {"consumed_at": datetime.now() - timedelta(days=2)}
        )
        db.session.commit()

        runner = app.test_cli_runner()
        result = runner.invoke(args=["delete_expired_refresh_tokens"])
        self.assertIn("Deleted", result.output)

        remaining = self._user_tokens()
        # deleted : the 100-day-old idle token and the token consumed 2
        # days ago ; kept : the successor of that refresh and the fresh login
        self.assertEqual(2, len(remaining))
        self.assertTrue(all(t.consumed_at is None for t in remaining))

    def test_logout_deletes_only_matching_token(self):
        login_1 = self._login()
        self._login()
        self.assertEqual(2, len(self._user_tokens()))

        with app.test_client() as c:
            response = c.post(
                "/token/logout",
                headers={"Authorization": f"Bearer {login_1['refreshToken']}"},
            )
            self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(self._user_tokens()))

        # replaying the logout with the same token must not wipe the
        # other sessions (regression : the old fallback deleted them all)
        with app.test_client() as c:
            response = c.post(
                "/token/logout",
                headers={"Authorization": f"Bearer {login_1['refreshToken']}"},
            )
            self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(self._user_tokens()))

    def test_logout_with_consumed_token_also_deletes_live_successor(self):
        login_data = self._login()
        old_token_string = decode_token(login_data["refreshToken"])[
            "identity"
        ]["token"]
        refresh_response = self._refresh(login_data["refreshToken"])
        self.assertIsNone(refresh_response.json.get("errors"))
        self.assertEqual(1, len(self._user_tokens(consumed=False)))
        self.assertEqual(1, len(self._user_tokens(consumed=True)))

        with app.test_client() as c:
            response = c.post(
                "/token/logout",
                headers={
                    "Authorization": f"Bearer {login_data['refreshToken']}"
                },
            )
            self.assertEqual(200, response.status_code)

        self.assertEqual(0, len(self._user_tokens()))
        self.assertIsNone(
            RefreshToken.query.filter_by(token=old_token_string).first()
        )

    def test_controller_refresh_token_consume_is_single_use(self):
        controller = ControllerUserFactory.create()
        token_string = ControllerRefreshToken.create_controller_refresh_token(
            controller
        )
        db.session.commit()

        first = ControllerRefreshToken.consume(token_string, controller.id)
        self.assertIsNotNone(first)
        second = ControllerRefreshToken.consume(token_string, controller.id)
        self.assertIsNone(second)
