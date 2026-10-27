from datetime import datetime, timedelta

from app import db
from app.models.user import UserAccountStatus
from app.seed.factories import CompanyFactory, UserFactory, EmploymentFactory
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestCompanyEmploymentsHideAnonymized(BaseTest):
    """
    Employments of anonymized users must not be returned to admins,
    not even as detached history rows (Trello card 2765).
    """

    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.anonymized_user = UserFactory.create(post__company=self.company)
        anonymized_employment = self.anonymized_user.employments[0]
        anonymized_employment.end_date = (
            datetime.now() - timedelta(days=365)
        ).date()
        self.anonymized_user.status = UserAccountStatus.ANONYMIZED
        db.session.commit()

    def _query_employments(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.admined_companies_employments,
            variables=dict(id=self.admin.id),
        )
        companies = response["data"]["user"]["adminedCompanies"]
        return companies[0]["employments"]

    def test_anonymized_user_employment_is_hidden(self):
        employments = self._query_employments()

        user_ids = [e["user"]["id"] for e in employments if e["user"]]
        self.assertIn(self.admin.id, user_ids)
        self.assertNotIn(self.anonymized_user.id, user_ids)
