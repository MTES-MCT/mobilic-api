from datetime import timedelta, date, datetime

from app.seed import CompanyFactory
from app.seed.factories import CompanyCertificationFactory, UserFactory
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestCertificateCompanyApi(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create(
            usual_name="company sans siret", siren="111111111"
        )
        self.admin_user = UserFactory.create(
            first_name="Tim",
            last_name="Leader",
            post__company=self.company,
            post__has_admin_rights=True,
        )

    def test_certificate(self):
        CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=10),
            expiration_date=date.today() + timedelta(days=10),
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )

        admined_companies = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_user.id,
            query=ApiRequests.admined_companies,
            unexposed_query=False,
            variables={
                "id": self.admin_user.id,
            },
        )
        admined_company = admined_companies["data"]["user"][
            "adminedCompanies"
        ][0]
        self.assertTrue(admined_company["isCertified"])
        self.assertIsNone(admined_company["acceptCertificationCommunication"])

    def test_no_certificate(self):
        CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=10),
            expiration_date=date.today() + timedelta(days=10),
            be_active=True,
            be_compliant=False,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )

        admined_companies = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_user.id,
            query=ApiRequests.admined_companies,
            unexposed_query=False,
            variables={
                "id": self.admin_user.id,
            },
        )
        admined_company = admined_companies["data"]["user"][
            "adminedCompanies"
        ][0]
        self.assertFalse(admined_company["isCertified"])
        self.assertIsNone(admined_company["acceptCertificationCommunication"])

    def test_expired_certificate(self):
        CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=10),
            expiration_date=date.today() - timedelta(days=4),
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )

        admined_companies = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_user.id,
            query=ApiRequests.admined_companies,
            unexposed_query=False,
            variables={
                "id": self.admin_user.id,
            },
        )
        admined_company = admined_companies["data"]["user"][
            "adminedCompanies"
        ][0]
        self.assertFalse(admined_company["isCertified"])
        self.assertIsNone(admined_company["acceptCertificationCommunication"])
