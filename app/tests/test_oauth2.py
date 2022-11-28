from app.tests import BaseTest
from app.helpers.oauth.models import OAuth2Client


class TestOAuth2(BaseTest):
    def setUp(self):
        super().setUp()

    def test_create_client(self):
        oauth2_client = OAuth2Client.create_client(
            name="test", redirect_uris="http://localhost:3000"
        )
        # print(oauth2_client)
        self.assertIsNotNone(oauth2_client)