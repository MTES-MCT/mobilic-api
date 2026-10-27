from unittest import TestCase

from app.helpers.mail import MailjetMessage
from app.helpers.mail_type import EmailType


class TestMailTemplateInjection(TestCase):
    def _variables(self, template_vars):
        message = MailjetMessage(
            EmailType.MANAGER_ONBOARDING_FIRST_INFO,
            recipient="worker@example.com",
            template_id=1,
            template_vars=template_vars,
        )
        return message.payload["Variables"]

    def test_expression_delimiters_are_stripped(self):
        variables = self._variables({"first_name": "{{7*7}}"})
        self.assertEqual(variables["first_name"], "7*7")

    def test_statement_delimiters_are_stripped(self):
        variables = self._variables(
            {"first_name": "{% for x in y %}z{% endfor %}"}
        )
        self.assertNotIn("{%", variables["first_name"])
        self.assertNotIn("%}", variables["first_name"])

    def test_data_reference_delimiters_are_stripped(self):
        variables = self._variables({"first_name": "[[data:email]]"})
        self.assertNotIn("[[", variables["first_name"])
        self.assertNotIn("]]", variables["first_name"])

    def test_reconstructed_delimiter_is_stripped(self):
        variables = self._variables({"first_name": "{}}{7*7}{{}"})
        self.assertNotIn("{{", variables["first_name"])
        self.assertNotIn("}}", variables["first_name"])

    def test_plain_value_is_untouched(self):
        variables = self._variables({"first_name": "Jean-Éric"})
        self.assertEqual(variables["first_name"], "Jean-Éric")
