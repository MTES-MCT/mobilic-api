from datetime import timedelta, date, datetime

from app import Company
from app.seed import CompanyFactory
from app.seed.factories import CompanyCertificationFactory, UserFactory
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests

EXPECTED_CERTIFICATION_DATE_FORMAT = "%Y/%m/%d"


class TestCertificateCommunicationApi(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create(usual_name="company")
        self.admin_user = UserFactory.create(
            first_name="Tim",
            last_name="Leader",
            post__company=self.company,
            post__has_admin_rights=True,
        )

    def test_certificate(self):
        make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_user.id,
            query=ApiRequests.edit_company_communication_setting,
            unexposed_query=True,
            variables={
                "companyIds": [self.company.id],
                "acceptCommunication": True,
            },
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
        self.assertTrue(admined_company["acceptCertificationCommunication"])
