import base64
import hashlib
import hmac
import json
from unittest import TestCase
from unittest.mock import patch

from app import app
from app.controllers.misc import parse_tally_csat
from app.helpers.brevo import BrevoApiClient, brevo


def _tally_csat_payload():
    return {
        "eventType": "FORM_RESPONSE",
        "createdAt": "2026-11-09T10:00:00.000Z",
        "data": {
            "responseId": "resp_1",
            "formId": "ODNQ0R",
            "createdAt": "2026-11-09T10:00:00.000Z",
            "fields": [
                {
                    "key": "q_email",
                    "label": "Email",
                    "type": "INPUT_EMAIL",
                    "value": "user@example.com",
                },
                {
                    "key": "q1",
                    "label": "Êtes-vous satisfait(e) de la réponse apportée "
                    "par le support Mobilic ?",
                    "type": "LINEAR_SCALE",
                    "value": 4,
                },
                {
                    "key": "q2",
                    "label": "Votre demande a-t-elle été résolue ?",
                    "type": "MULTIPLE_CHOICE",
                    "value": ["opt_a"],
                    "options": [
                        {"id": "opt_a", "text": "Oui, complètement"},
                        {"id": "opt_b", "text": "Non"},
                    ],
                },
                {
                    "key": "q3",
                    "label": "Comment évaluez-vous la qualité de "
                    "l'accompagnement reçu ?",
                    "type": "LINEAR_SCALE",
                    "value": 5,
                },
                {
                    "key": "q4",
                    "label": "Avez-vous un commentaire ou une suggestion "
                    "pour améliorer notre support ?",
                    "type": "TEXTAREA",
                    "value": "Super support",
                },
            ],
        },
    }


class TestSanitizeCompanyName(TestCase):
    def setUp(self):
        self.client = BrevoApiClient(api_key="dummy-key")

    def test_none_returns_unknown_company(self):
        self.assertEqual(
            "Unknown Company", self.client.sanitize_company_name(None)
        )

    def test_empty_string_returns_unknown_company(self):
        self.assertEqual(
            "Unknown Company", self.client.sanitize_company_name("")
        )

    def test_whitespace_only_returns_unknown_company(self):
        self.assertEqual(
            "Unknown Company", self.client.sanitize_company_name("   ")
        )

    def test_strips_leading_and_trailing_whitespace(self):
        self.assertEqual(
            "My Company",
            self.client.sanitize_company_name("  My Company  "),
        )

    def test_collapses_internal_whitespace(self):
        self.assertEqual(
            "My Company",
            self.client.sanitize_company_name("My    Company"),
        )

    def test_replaces_problematic_characters_with_space(self):
        name = "My\"Company'Name’Here\nWith\rTabs\tToo"
        self.assertEqual(
            "My Company Name Here With Tabs Too",
            self.client.sanitize_company_name(name),
        )

    def test_name_within_limit_is_unchanged(self):
        name = "A" * 100
        self.assertEqual(name, self.client.sanitize_company_name(name))

    def test_name_over_limit_is_truncated_with_ellipsis(self):
        name = "A" * 150
        result = self.client.sanitize_company_name(name)
        self.assertEqual(100, len(result))
        self.assertEqual("A" * 97 + "...", result)

    def test_name_becoming_empty_after_cleaning_returns_unknown_company(self):
        name = "\"'’"
        self.assertEqual(
            "Unknown Company", self.client.sanitize_company_name(name)
        )


class TestParseTallyCsat(TestCase):
    def test_maps_all_answers(self):
        email, attributes = parse_tally_csat(_tally_csat_payload())
        self.assertEqual("user@example.com", email)
        self.assertEqual(4, attributes["CSAT_SUPPORT_SATISFACTION"])
        self.assertEqual(5, attributes["CSAT_SUPPORT_QUALITY"])
        self.assertEqual(
            "Oui, complètement", attributes["CSAT_SUPPORT_RESOLVED"]
        )
        self.assertEqual("Super support", attributes["CSAT_SUPPORT_COMMENT"])
        self.assertEqual("2026-11-09", attributes["CSAT_SUPPORT_DATE"])

    def test_email_from_hidden_field(self):
        payload = _tally_csat_payload()
        payload["data"]["fields"][0] = {
            "key": "email",
            "label": "email",
            "type": "HIDDEN_FIELDS",
            "value": "hidden@example.com",
        }
        email, _ = parse_tally_csat(payload)
        self.assertEqual("hidden@example.com", email)

    def test_label_reword_still_maps_scores(self):
        payload = _tally_csat_payload()
        payload["data"]["fields"][1]["label"] = "Votre satisfaction globale"
        payload["data"]["fields"][3]["label"] = "Qualité de l'accompagnement"
        _, attributes = parse_tally_csat(payload)
        self.assertEqual(4, attributes["CSAT_SUPPORT_SATISFACTION"])
        self.assertEqual(5, attributes["CSAT_SUPPORT_QUALITY"])

    def test_optional_comment_absent(self):
        payload = _tally_csat_payload()
        payload["data"]["fields"] = [
            f for f in payload["data"]["fields"] if f["type"] != "TEXTAREA"
        ]
        _, attributes = parse_tally_csat(payload)
        self.assertNotIn("CSAT_SUPPORT_COMMENT", attributes)

    def test_missing_email_returns_none(self):
        payload = _tally_csat_payload()
        payload["data"]["fields"] = [
            f for f in payload["data"]["fields"] if f["type"] != "INPUT_EMAIL"
        ]
        email, _ = parse_tally_csat(payload)
        self.assertIsNone(email)

    def test_empty_payload(self):
        email, attributes = parse_tally_csat({})
        self.assertIsNone(email)
        self.assertEqual({}, attributes)


class TestTallyCsatWebhook(TestCase):
    SECRET = "test-secret"

    def _sign(self, body: bytes) -> str:
        return base64.b64encode(
            hmac.new(self.SECRET.encode(), body, hashlib.sha256).digest()
        ).decode()

    def _post(self, body: bytes, signature: str):
        with app.test_client() as c:
            return c.post(
                "/webhooks/tally-csat",
                data=body,
                content_type="application/json",
                headers={"Tally-Signature": signature},
            )

    def test_valid_signature_upserts_and_returns_204(self):
        body = json.dumps(_tally_csat_payload()).encode()
        with patch.dict(app.config, {"TALLY_WEBHOOK_SECRET": self.SECRET}):
            with patch.object(brevo, "upsert_contact_attributes") as upsert:
                resp = self._post(body, self._sign(body))
        self.assertEqual(204, resp.status_code)
        upsert.assert_called_once()
        email, attributes = upsert.call_args[0]
        self.assertEqual("user@example.com", email)
        self.assertEqual(4, attributes["CSAT_SUPPORT_SATISFACTION"])

    def test_missing_secret_returns_503(self):
        body = json.dumps(_tally_csat_payload()).encode()
        with patch.dict(app.config, {"TALLY_WEBHOOK_SECRET": None}):
            with patch.object(brevo, "upsert_contact_attributes") as upsert:
                resp = self._post(body, self._sign(body))
        self.assertEqual(503, resp.status_code)
        upsert.assert_not_called()

    def test_invalid_signature_returns_403(self):
        body = json.dumps(_tally_csat_payload()).encode()
        with patch.dict(app.config, {"TALLY_WEBHOOK_SECRET": self.SECRET}):
            with patch.object(brevo, "upsert_contact_attributes") as upsert:
                resp = self._post(body, "not-the-right-signature")
        self.assertEqual(403, resp.status_code)
        upsert.assert_not_called()

    def test_incomplete_payload_returns_422_without_upsert(self):
        payload = _tally_csat_payload()
        payload["data"]["fields"] = [
            f
            for f in payload["data"]["fields"]
            if "satisfait" not in f["label"].lower()
        ]
        body = json.dumps(payload).encode()
        with patch.dict(app.config, {"TALLY_WEBHOOK_SECRET": self.SECRET}):
            with patch.object(brevo, "upsert_contact_attributes") as upsert:
                resp = self._post(body, self._sign(body))
        self.assertEqual(422, resp.status_code)
        upsert.assert_not_called()
