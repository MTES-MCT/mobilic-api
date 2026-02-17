from unittest.mock import patch

from app import app
from app.domain.controller import check_idp_allowed
from app.helpers.errors import AgentConnectIdpNotAllowedError
from app.tests import BaseTest


class TestCheckIdpAllowed(BaseTest):
    def test_blocks_when_allowlist_empty(self):
        with app.app_context():
            app.config["PC_ALLOWED_IDP_IDS"] = []
            with self.assertRaises(AgentConnectIdpNotAllowedError):
                check_idp_allowed({"idp_id": "some-idp"})

    def test_blocks_when_idp_not_in_allowlist(self):
        with app.app_context():
            app.config["PC_ALLOWED_IDP_IDS"] = ["allowed-idp"]
            with self.assertRaises(AgentConnectIdpNotAllowedError):
                check_idp_allowed({"idp_id": "other-idp"})

    def test_allows_when_idp_in_allowlist(self):
        with app.app_context():
            app.config["PC_ALLOWED_IDP_IDS"] = ["allowed-idp"]
            check_idp_allowed({"idp_id": "allowed-idp"})

    def test_blocks_when_idp_id_missing(self):
        with app.app_context():
            app.config["PC_ALLOWED_IDP_IDS"] = ["allowed-idp"]
            with self.assertRaises(AgentConnectIdpNotAllowedError):
                check_idp_allowed({})

    def test_allows_with_multiple_idps_in_allowlist(self):
        with app.app_context():
            app.config["PC_ALLOWED_IDP_IDS"] = ["idp-1", "idp-2", "idp-3"]
            check_idp_allowed({"idp_id": "idp-2"})
