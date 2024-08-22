from app.helpers.validation import validate_clean_email_string
from app.tests import BaseTest


class TestEmailValidation(BaseTest):
    def test_email_validation_works(self):
        valid_emails = [
            "prenom.nom@beta.gouv.fr",
            "prenom.nom@gmail.com",
            "prenom.nom@developpement-durable.gouv.fr",
            "nepasrepondre@mobilic.beta.gouv.fr",
            "prenom.nom+123@hotmail.fr",
            "prenom-nom@domain-with-dash.fr",
            "prenom123nom@domain456.sth",
            "prenom_123_nom@do.main",
        ]
        invalid_emails = [
            "prenom",
            "prenom.nom",
            "@domain.fr" "prenom.nom@domain",
            "prenom.nom@do@main",
            "prenom&(45)@do.main",
            "prenom.nom@.main",
            "prenom.nom@main.",
        ]
        for email in valid_emails:
            self.assertEqual(validate_clean_email_string(email), True)
        for email in invalid_emails:
            self.assertEqual(validate_clean_email_string(email), False)
