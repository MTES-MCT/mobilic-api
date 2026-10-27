from app.seed import CompanyFactory, UserFactory
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request

QUERY = """
  query bola($id: Int!, $companyIds: [Int]) {
    user(id: $id) {
      adminedCompanies(companyIds: $companyIds) {
        id
      }
    }
  }
"""


class TestAdminedCompaniesAuthorization(BaseTest):
    def setUp(self):
        super().setUp()
        self.company_a = CompanyFactory.create()
        self.admin_a = UserFactory.create(
            post__company=self.company_a, post__has_admin_rights=True
        )
        self.company_b = CompanyFactory.create()
        self.admin_b = UserFactory.create(
            post__company=self.company_b, post__has_admin_rights=True
        )
        self.employee_b = UserFactory.create(
            post__company=self.company_b, post__has_admin_rights=False
        )

    def _admined_ids(self, user, company_ids):
        response = make_authenticated_request(
            time=None,
            submitter_id=user.id,
            query=QUERY,
            variables={"id": user.id, "company_ids": company_ids},
        )
        return [c["id"] for c in response["data"]["user"]["adminedCompanies"]]

    def test_company_ids_cannot_return_foreign_company(self):
        # The BOLA: admin of B naming company A must not receive it.
        self.assertEqual(
            self._admined_ids(self.admin_b, [self.company_a.id]), []
        )

    def test_company_ids_is_a_filter_not_a_source(self):
        ids = self._admined_ids(
            self.admin_a, [self.company_a.id, self.company_b.id]
        )
        self.assertEqual(ids, [self.company_a.id])

    def test_own_company_still_returned_when_named(self):
        self.assertEqual(
            self._admined_ids(self.admin_a, [self.company_a.id]),
            [self.company_a.id],
        )

    def test_no_argument_returns_all_admined_companies(self):
        self.assertEqual(
            self._admined_ids(self.admin_a, None), [self.company_a.id]
        )

    def test_employee_without_admin_rights_gets_nothing(self):
        self.assertEqual(
            self._admined_ids(self.employee_b, [self.company_b.id]), []
        )
