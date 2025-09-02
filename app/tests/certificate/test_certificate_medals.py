from unittest import TestCase

from app.models import CompanyCertification
from app.models.company_certification import CertificationLevel


class TestCertificateMedals(TestCase):

    def test_medals(self):
        certification = CompanyCertification(
            log_in_real_time=0.62, admin_changes=0.28, compliancy=0
        )
        self.assertEqual(
            certification.certification_level, CertificationLevel.BRONZE
        )

        certification.admin_changes = 0.32
        self.assertEqual(
            certification.certification_level,
            CertificationLevel.NO_CERTIFICATION,
        )

        certification.admin_changes = 0.18
        certification.log_in_real_time = 0.62
        self.assertEqual(
            certification.certification_level, CertificationLevel.BRONZE
        )

        certification.compliancy = 2
        certification.log_in_real_time = 0.72
        self.assertEqual(
            certification.certification_level, CertificationLevel.SILVER
        )

        certification.admin_changes = 0.02
        certification.log_in_real_time = 0.93
        certification.compliancy = 6
        self.assertEqual(
            certification.certification_level, CertificationLevel.GOLD
        )

        certification.admin_changes = 0.005
        certification.log_in_real_time = 0.96
        certification.compliancy = 6
        self.assertEqual(
            certification.certification_level, CertificationLevel.DIAMOND
        )

        certification.admin_changes = 0.005
        certification.log_in_real_time = 0.96
        certification.compliancy = 0
        self.assertEqual(
            certification.certification_level, CertificationLevel.BRONZE
        )
