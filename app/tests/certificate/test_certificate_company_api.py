from datetime import timedelta, date, datetime
from dateutil.relativedelta import relativedelta

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
        certificate = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=31),
            expiration_date=date.today() + timedelta(days=31),
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
        self.assertEqual(
            certificate.attribution_date,
            datetime.strptime(
                admined_company["startLastCertificationPeriod"], "%Y-%m-%d"
            ).date(),
        )

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
        self.assertIsNone(admined_company["lastDayCertified"])
        self.assertIsNone(admined_company["startLastCertificationPeriod"])

    def test_expired_certificate(self):
        expired_certificate = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=62),
            expiration_date=date.today() - timedelta(days=31),
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
        self.assertEqual(
            expired_certificate.expiration_date,
            datetime.strptime(
                admined_company["lastDayCertified"], "%Y-%m-%d"
            ).date(),
        )
        self.assertEqual(
            expired_certificate.attribution_date,
            datetime.strptime(
                admined_company["startLastCertificationPeriod"], "%Y-%m-%d"
            ).date(),
        )

    def test_certificate_renewed(self):
        old_certificate = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date(2020, 1, 1),
            expiration_date=date(2020, 6, 30),
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )

        today = date.today()
        first_day_of_month = date(today.year, today.month, 1)
        last_day_of_previous_month = first_day_of_month - timedelta(days=1)
        first_day_of_six_month_ago = first_day_of_month - relativedelta(
            months=6
        )
        last_day_of_six_month_ahead = (
            first_day_of_month
            + relativedelta(months=7)
            - relativedelta(days=1)
        )

        previous_continuous_certificate = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=first_day_of_six_month_ago,
            expiration_date=last_day_of_previous_month,
            be_active=True,
            be_compliant=True,
            not_too_many_changes=True,
            validate_regularly=True,
            log_in_real_time=True,
        )

        current_certificate = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=first_day_of_month,
            expiration_date=last_day_of_six_month_ahead,
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
        self.assertEqual(
            previous_continuous_certificate.attribution_date,
            datetime.strptime(
                admined_company["startLastCertificationPeriod"], "%Y-%m-%d"
            ).date(),
        )
