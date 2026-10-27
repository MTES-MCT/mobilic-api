from argon2 import PasswordHasher

from app import db
from app.helpers.api_key_authentication import (
    check_api_key,
    API_KEY_HTTP_HEADER_NAME,
)
from app.helpers.authentication import (
    CLIENT_ID_HTTP_HEADER_NAME,
    verify_oauth_token_in_request,
)
from app.helpers.errors import ClientSuspendedError
from app.helpers.oauth import get_or_create_token
from app.helpers.oauth.models import OAuth2Client
from app.seed.factories import (
    ThirdPartyApiKeyFactory,
    UserFactory,
)
from app.tests import BaseTest, app
from app.tests.helpers import ApiRequests, make_protected_request


class TestOAuthClientSuspensionViaApiKey(BaseTest):
    def setUp(self):
        super().setUp()

        oauth2_client = OAuth2Client.create_client(
            name="test_client", redirect_uris="http://localhost:3000"
        )
        self.oauth2_client = oauth2_client
        self.client_id = oauth2_client.get_client_id()

        raw_api_key = (
            "012345678901234567890123456789012345678901234567890123456789"
        )
        ph = PasswordHasher()
        ThirdPartyApiKeyFactory.create(
            client=oauth2_client, api_key=ph.hash(raw_api_key)
        )
        self.api_key_header = "mobilic_live_" + raw_api_key

        make_protected_request(
            query=ApiRequests.software_registration,
            variables=dict(
                client_id=self.client_id,
                usual_name="Test",
                siren="123456789",
                nb_workers=10,
            ),
            headers={
                CLIENT_ID_HTTP_HEADER_NAME: self.client_id,
                API_KEY_HTTP_HEADER_NAME: self.api_key_header,
            },
        )

    def _ctx(self):
        return app.test_request_context(
            "/protected",
            headers={
                CLIENT_ID_HTTP_HEADER_NAME: str(self.client_id),
                API_KEY_HTTP_HEADER_NAME: self.api_key_header,
            },
        )

    def _suspend(self):
        # db.engine.execute uses autocommit, guaranteeing immediate DB visibility
        db.engine.execute(
            f"UPDATE oauth2_client SET suspended_at = NOW() WHERE id = {self.client_id}"
        )

    def _unsuspend(self):
        db.engine.execute(
            f"UPDATE oauth2_client SET suspended_at = NULL WHERE id = {self.client_id}"
        )

    def test_active_client_can_make_api_requests(self):
        with self._ctx():
            self.assertTrue(check_api_key())

    def test_suspended_client_api_key_request_is_blocked(self):
        self._suspend()
        with self._ctx():
            with self.assertRaises(ClientSuspendedError):
                check_api_key()

    def test_unsuspended_client_can_make_api_requests_again(self):
        self._suspend()
        with self._ctx():
            with self.assertRaises(ClientSuspendedError):
                check_api_key()
        self._unsuspend()
        with self._ctx():
            self.assertTrue(check_api_key())


class TestOAuthClientSuspensionViaOAuthToken(BaseTest):
    def setUp(self):
        super().setUp()

        oauth2_client = OAuth2Client.create_client(
            name="test_client_oauth", redirect_uris="http://localhost:3000"
        )
        self.oauth2_client = oauth2_client
        self.user = UserFactory.create()
        token_dict = get_or_create_token(oauth2_client, "", user=self.user)
        self.token_string = token_dict["access_token"]

    def _suspend(self):
        db.engine.execute(
            f"UPDATE oauth2_client SET suspended_at = NOW() WHERE id = {self.oauth2_client.id}"
        )

    def _unsuspend(self):
        db.engine.execute(
            f"UPDATE oauth2_client SET suspended_at = NULL WHERE id = {self.oauth2_client.id}"
        )

    def test_active_client_oauth_token_is_accepted(self):
        with app.test_request_context(
            "/graphql",
            headers={"Authorization": f"Bearer {self.token_string}"},
        ):
            verify_oauth_token_in_request()

    def test_suspended_client_oauth_token_is_blocked(self):
        self._suspend()
        with app.test_request_context(
            "/graphql",
            headers={"Authorization": f"Bearer {self.token_string}"},
        ):
            with self.assertRaises(ClientSuspendedError):
                verify_oauth_token_in_request()

    def test_unsuspended_client_oauth_token_is_accepted_again(self):
        self._suspend()
        with app.test_request_context(
            "/graphql",
            headers={"Authorization": f"Bearer {self.token_string}"},
        ):
            with self.assertRaises(ClientSuspendedError):
                verify_oauth_token_in_request()

        self._unsuspend()
        db.session.expire_all()
        with app.test_request_context(
            "/graphql",
            headers={"Authorization": f"Bearer {self.token_string}"},
        ):
            verify_oauth_token_in_request()
