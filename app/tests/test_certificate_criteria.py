from unittest import TestCase

from app.domain.certificate_criteria import be_active


class TestCertificateCriteria(TestCase):
    def test_be_active(self):
        company = None
        result = be_active(company)
        self.assertFalse(result)
