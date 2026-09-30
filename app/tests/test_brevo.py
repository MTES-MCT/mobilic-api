from unittest import TestCase

from app.helpers.brevo import BrevoApiClient


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
