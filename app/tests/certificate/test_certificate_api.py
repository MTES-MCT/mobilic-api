from datetime import timedelta, date

from app.seed import CompanyFactory
from app.seed.factories import CompanyCertificationFactory
from app.tests import test_post_rest, BaseTest
from config import TestConfig

EXPECTED_CERTIFICATION_DATE_FORMAT = "%Y/%m/%d"


class TestCertificateApi(BaseTest):
    def setUp(self):
        super().setUp()
        self.company_without_siret = CompanyFactory.create(
            usual_name="company sans siret",
            siren="111111111",
            accept_certification_communication=True,
        )

        self.company_with_sirets = CompanyFactory.create(
            usual_name="company avec sirets",
            siren="222222222",
            short_sirets=[333, 4444],
            accept_certification_communication=True,
        )

        self.company_with_other_sirets = CompanyFactory.create(
            usual_name="company avec un autre siret",
            siren="222222222",
            short_sirets=[55555],
            accept_certification_communication=True,
        )

    def test_certificate_no_header(self):
        company_certification = test_post_rest(
            "/companies/is_company_certified",
            json={
                "siren": self.company_without_siret.siren,
            },
            headers={},
        )
        self.assertEqual(company_certification.status_code, 401)

    def test_certificate_bad_header(self):
        company_certification = test_post_rest(
            "/companies/is_company_certified",
            json={
                "siren": self.company_without_siret.siren,
            },
            headers={
                "X-MOBILIC-CERTIFICATION-KEY": "a",
            },
        )
        self.assertEqual(company_certification.status_code, 401)

    def test_certificate_no_siret(self):
        certification = CompanyCertificationFactory.create(
            company_id=self.company_without_siret.id,
            attribution_date=date.today() - timedelta(days=30),
            expiration_date=date.today() + timedelta(days=30),
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )
        company_certification = test_post_rest(
            "/companies/is_company_certified",
            json={
                "siren": self.company_without_siret.siren,
            },
            headers={
                "X-MOBILIC-CERTIFICATION-KEY": TestConfig.CERTIFICATION_API_KEY,
            },
        )
        self.assertEqual(company_certification.status_code, 200)
        list_certified_companies = company_certification.json
        self.assertEqual(1, len(list_certified_companies))
        self.assertEqual(
            self.company_without_siret.siren,
            list_certified_companies[0]["siren"],
        )
        self.assertEqual(
            certification.attribution_date.strftime(
                EXPECTED_CERTIFICATION_DATE_FORMAT
            ),
            list_certified_companies[0]["certification_attribution_date"],
        )
        self.assertEqual(
            certification.expiration_date.strftime(
                EXPECTED_CERTIFICATION_DATE_FORMAT
            ),
            list_certified_companies[0]["certification_expiration_date"],
        )

    def test_certificate_with_siret(self):
        certification_1 = CompanyCertificationFactory.create(
            company_id=self.company_with_sirets.id,
            attribution_date=date.today() - timedelta(days=10),
            expiration_date=date.today() + timedelta(days=10),
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )
        certification_2 = CompanyCertificationFactory.create(
            company_id=self.company_with_other_sirets.id,
            attribution_date=date.today() - timedelta(days=30),
            expiration_date=date.today() + timedelta(days=30),
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )
        company_certification = test_post_rest(
            "/companies/is_company_certified",
            json={
                "siren": self.company_with_sirets.siren,
            },
            headers={
                "X-MOBILIC-CERTIFICATION-KEY": TestConfig.CERTIFICATION_API_KEY,
            },
        )
        self.assertEqual(company_certification.status_code, 200)
        list_certified_companies = company_certification.json
        self.assertEqual(3, len(list_certified_companies))
        self.assertEqual(
            self.company_with_sirets.siren,
            list_certified_companies[0]["siren"],
        )
        self.assertEqual(
            "22222222200333", list_certified_companies[0]["siret"]
        )
        self.assertEqual(
            certification_1.attribution_date.strftime(
                EXPECTED_CERTIFICATION_DATE_FORMAT
            ),
            list_certified_companies[0]["certification_attribution_date"],
        )
        self.assertEqual(
            certification_1.expiration_date.strftime(
                EXPECTED_CERTIFICATION_DATE_FORMAT
            ),
            list_certified_companies[0]["certification_expiration_date"],
        )
        self.assertEqual(
            self.company_with_sirets.siren,
            list_certified_companies[1]["siren"],
        )
        self.assertEqual(
            "22222222204444", list_certified_companies[1]["siret"]
        )
        self.assertEqual(
            certification_1.attribution_date.strftime(
                EXPECTED_CERTIFICATION_DATE_FORMAT
            ),
            list_certified_companies[1]["certification_attribution_date"],
        )
        self.assertEqual(
            certification_1.expiration_date.strftime(
                EXPECTED_CERTIFICATION_DATE_FORMAT
            ),
            list_certified_companies[1]["certification_expiration_date"],
        )
        self.assertEqual(
            self.company_with_sirets.siren,
            list_certified_companies[2]["siren"],
        )
        self.assertEqual(
            "22222222255555", list_certified_companies[2]["siret"]
        )
        self.assertEqual(
            certification_2.attribution_date.strftime(
                EXPECTED_CERTIFICATION_DATE_FORMAT
            ),
            list_certified_companies[2]["certification_attribution_date"],
        )
        self.assertEqual(
            certification_2.expiration_date.strftime(
                EXPECTED_CERTIFICATION_DATE_FORMAT
            ),
            list_certified_companies[2]["certification_expiration_date"],
        )

    def test_expired_certificate(self):
        CompanyCertificationFactory.create(
            company_id=self.company_without_siret.id,
            attribution_date=date.today() - timedelta(days=30),
            expiration_date=date.today() - timedelta(days=15),
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )
        company_certification = test_post_rest(
            "/companies/is_company_certified",
            json={
                "siren": "111111111",
            },
            headers={
                "X-MOBILIC-CERTIFICATION-KEY": TestConfig.CERTIFICATION_API_KEY,
            },
        )
        self.assertEqual(company_certification.status_code, 200)
        list_certified_companies = company_certification.json
        self.assertEqual(0, len(list_certified_companies))

    def test_no_certificate(self):
        company_certification = test_post_rest(
            "/companies/is_company_certified",
            json={
                "siren": "123456789",
            },
            headers={
                "X-MOBILIC-CERTIFICATION-KEY": TestConfig.CERTIFICATION_API_KEY,
            },
        )
        self.assertEqual(company_certification.status_code, 200)
        list_certified_companies = company_certification.json
        self.assertEqual(0, len(list_certified_companies))

    def test_decline_communication(self):
        company_no_communication = CompanyFactory.create(
            usual_name="company refuse comm",
            siren="111111111",
            accept_certification_communication=False,
        )
        CompanyCertificationFactory.create(
            company_id=company_no_communication.id,
            attribution_date=date.today() - timedelta(days=30),
            expiration_date=date.today() + timedelta(days=30),
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )
        company_certification = test_post_rest(
            "/companies/is_company_certified",
            json={
                "siren": company_no_communication.siren,
            },
            headers={
                "X-MOBILIC-CERTIFICATION-KEY": TestConfig.CERTIFICATION_API_KEY,
            },
        )
        self.assertEqual(company_certification.status_code, 200)
        list_certified_companies = company_certification.json
        self.assertEqual(0, len(list_certified_companies))

    def test_no_communication_information(self):
        company_no_communication = CompanyFactory.create(
            usual_name="company no comm info",
            siren="111111111",
            accept_certification_communication=None,
        )
        CompanyCertificationFactory.create(
            company_id=company_no_communication.id,
            attribution_date=date.today() - timedelta(days=30),
            expiration_date=date.today() + timedelta(days=30),
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )
        company_certification = test_post_rest(
            "/companies/is_company_certified",
            json={
                "siren": company_no_communication.siren,
            },
            headers={
                "X-MOBILIC-CERTIFICATION-KEY": TestConfig.CERTIFICATION_API_KEY,
            },
        )
        self.assertEqual(company_certification.status_code, 200)
        list_certified_companies = company_certification.json
        self.assertEqual(0, len(list_certified_companies))
