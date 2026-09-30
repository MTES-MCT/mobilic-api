import unittest

from app.helpers.brevo import BrevoApiClient
from app.services.brevo.orchestrator import BrevoSyncOrchestrator


class BrevoDealLookupSymmetryTestCase(unittest.TestCase):
    """Regression: deals_by_identifier must sanitize the deal name so that
    the map keys match what _find_existing_deal computes at lookup time.
    Without this, deals created before a sanitize rule change (e.g. adding
    U+2019) get re-duplicated on the next sync.
    """

    def setUp(self):
        self.client = BrevoApiClient(api_key="test-key")
        self.orchestrator = BrevoSyncOrchestrator(self.client)

    def test_sanitize_strips_typographic_and_ascii_apostrophes(self):
        for raw in ["TIA’FRET", "TIA'FRET", "Ruet’express"]:
            with self.subTest(raw=raw):
                self.assertNotIn("'", self.client.sanitize_company_name(raw))
                self.assertNotIn("’", self.client.sanitize_company_name(raw))

    def test_lookup_matches_deal_stored_with_typographic_apostrophe(self):
        # A deal created before the sanitize change still has its raw
        # typographic apostrophe in Brevo. The lookup uses the fresh DB
        # name which the new sanitize normalizes. Both keys must align.
        raw_brevo_name = "TIA’FRET"
        deals_by_identifier = self.orchestrator._build_deals_by_identifier(
            [{"id": "deal-1", "name": raw_brevo_name}]
        )

        existing, key = self.orchestrator._find_existing_deal(
            {"company_name": raw_brevo_name}, deals_by_identifier
        )

        self.assertIsNotNone(existing)
        self.assertEqual(existing["id"], "deal-1")
        self.assertEqual(key, "name_TIA FRET")
