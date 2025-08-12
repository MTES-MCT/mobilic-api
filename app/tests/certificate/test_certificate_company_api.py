from datetime import timedelta, date, datetime
from dateutil.relativedelta import relativedelta

from app import get_current_certificate
from app.models.company_certification import (
    CERTIFICATION_ADMIN_CHANGES_SILVER,
    CERTIFICATION_REAL_TIME_SILVER,
    CERTIFICATION_COMPLIANCY_SILVER,
    CERTIFICATION_REAL_TIME_BRONZE,
    CERTIFICATION_ADMIN_CHANGES_BRONZE,
    CertificationLevel,
)
from app.seed import CompanyFactory
from app.seed.factories import CompanyCertificationFactory, UserFactory
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests

silver_certif_args = dict(
    log_in_real_time=CERTIFICATION_REAL_TIME_SILVER,
    admin_changes=CERTIFICATION_ADMIN_CHANGES_SILVER,
    compliancy=CERTIFICATION_COMPLIANCY_SILVER,
)
no_certif_args = dict(
    log_in_real_time=CERTIFICATION_REAL_TIME_BRONZE - 0.1,
    admin_changes=CERTIFICATION_ADMIN_CHANGES_SILVER,
    compliancy=CERTIFICATION_COMPLIANCY_SILVER,
)


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
            **silver_certif_args,
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
        certification = admined_company["currentCompanyCertification"]
        self.assertTrue(certification["isCertified"])
        self.assertIsNone(admined_company["acceptCertificationCommunication"])
        self.assertEqual(
            certificate.attribution_date,
            datetime.strptime(
                certification["startLastCertificationPeriod"], "%Y-%m-%d"
            ).date(),
        )

    def test_no_certificate(self):
        CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=10),
            expiration_date=date.today() + timedelta(days=10),
            **no_certif_args,
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
        certification = admined_company["currentCompanyCertification"]
        self.assertFalse(certification["isCertified"])
        self.assertIsNone(admined_company["acceptCertificationCommunication"])
        self.assertIsNone(certification["lastDayCertified"])
        self.assertIsNone(certification["startLastCertificationPeriod"])

    def test_expired_certificate(self):
        expired_certificate = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=62),
            expiration_date=date.today() - timedelta(days=31),
            **silver_certif_args,
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
        certification = admined_company["currentCompanyCertification"]
        self.assertFalse(certification["isCertified"])
        self.assertIsNone(admined_company["acceptCertificationCommunication"])
        self.assertEqual(
            expired_certificate.expiration_date,
            datetime.strptime(
                certification["lastDayCertified"], "%Y-%m-%d"
            ).date(),
        )
        self.assertEqual(
            expired_certificate.attribution_date,
            datetime.strptime(
                certification["startLastCertificationPeriod"], "%Y-%m-%d"
            ).date(),
        )

    def test_certificate_renewed(self):
        old_certificate = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date(2020, 1, 1),
            expiration_date=date(2020, 6, 30),
            **silver_certif_args,
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
            **silver_certif_args,
        )

        current_certificate = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=first_day_of_month,
            expiration_date=last_day_of_six_month_ahead,
            **silver_certif_args,
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
        certification = admined_company["currentCompanyCertification"]
        self.assertTrue(certification["isCertified"])
        self.assertIsNone(admined_company["acceptCertificationCommunication"])
        self.assertEqual(
            previous_continuous_certificate.attribution_date,
            datetime.strptime(
                certification["startLastCertificationPeriod"], "%Y-%m-%d"
            ).date(),
        )

    def test_current_certificate_medals(self):
        # silver certif two months ago, still valid today
        silver_certificate = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=62),
            expiration_date=date.today() + timedelta(days=10),
            **silver_certif_args,
        )

        # bronze certif valid and more recent
        CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=31),
            expiration_date=date.today() + timedelta(days=40),
            log_in_real_time=CERTIFICATION_REAL_TIME_BRONZE,
            admin_changes=CERTIFICATION_ADMIN_CHANGES_BRONZE,
            compliancy=CERTIFICATION_COMPLIANCY_SILVER,
        )

        current_certificate = get_current_certificate(self.company.id)
        self.assertEqual(current_certificate.id, silver_certificate.id)

    def test_current_certificate_dates(self):
        # silver certif two months ago, still valid today
        CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=62),
            expiration_date=date.today() + timedelta(days=10),
            **silver_certif_args,
        )

        # another silver certif valid and more recent
        silver_certificate_2 = CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=31),
            expiration_date=date.today() + timedelta(days=40),
            **silver_certif_args,
        )

        current_certificate = get_current_certificate(self.company.id)
        self.assertEqual(current_certificate.id, silver_certificate_2.id)

    def test_certificate_criterias(self):
        CompanyCertificationFactory.create(
            company_id=self.company.id,
            attribution_date=date.today() - timedelta(days=62),
            expiration_date=date.today() + timedelta(days=10),
            **silver_certif_args,
        )
        res = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_user.id,
            query=ApiRequests.admined_companies_certificate,
            unexposed_query=False,
            variables={
                "id": self.admin_user.id,
            },
        )
        res = res["data"]["user"]["adminedCompanies"][0]
        current_company_certification = res["currentCompanyCertification"]
        certificate_criterias = current_company_certification[
            "certificateCriterias"
        ]
        current_medal = current_company_certification["certificationMedal"]

        self.assertEqual(
            certificate_criterias["logInRealTime"],
            CERTIFICATION_REAL_TIME_SILVER,
        )
        self.assertEqual(
            certificate_criterias["adminChanges"],
            CERTIFICATION_ADMIN_CHANGES_SILVER,
        )
        self.assertEqual(current_medal, CertificationLevel.SILVER.name)
