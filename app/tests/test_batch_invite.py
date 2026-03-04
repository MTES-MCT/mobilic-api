from app.seed import CompanyFactory, UserFactory
from app.tests import BaseTest, test_post_graphql
from app.models.employment import (
    Employment,
    EmploymentRequestValidationStatus,
)
from app.tests.helpers import ApiRequests


BATCH_INVITE_MUTATION = """
    mutation (
        $companyId: Int!,
        $mails: [Email],
        $userIds: [Int]
    ) {
        employments {
            batchCreateWorkerEmployments(
                companyId: $companyId,
                mails: $mails,
                userIds: $userIds
            ) {
                id
                userId
                email
                hideEmail
            }
        }
    }
"""


def batch_invite(admin, company_id, mails=None, user_ids=None):
    variables = {"companyId": company_id}
    if mails is not None:
        variables["mails"] = mails
    if user_ids is not None:
        variables["userIds"] = user_ids
    return test_post_graphql(
        BATCH_INVITE_MUTATION,
        mock_authentication_with_user=admin,
        variables=variables,
    )


class TestBatchInvite(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.employee_1 = UserFactory.create()
        self.employee_2 = UserFactory.create()

    def _get_result(self, response):
        return (
            response.json.get("data", {})
            .get("employments", {})
            .get("batchCreateWorkerEmployments")
        )

    def test_batch_invite_emails_only(self):
        mails = ["user1@test.com", "user2@test.com"]
        response = batch_invite(self.admin, self.company.id, mails=mails)

        result = self._get_result(response)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)

        employments = Employment.query.filter_by(
            company_id=self.company.id,
            validation_status=EmploymentRequestValidationStatus.PENDING,
        ).all()
        email_employments = [e for e in employments if e.email in mails]
        self.assertEqual(len(email_employments), 2)

    def test_batch_invite_user_ids_only(self):
        user_ids = [self.employee_1.id, self.employee_2.id]
        response = batch_invite(self.admin, self.company.id, user_ids=user_ids)

        result = self._get_result(response)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)

        for emp_data in result:
            self.assertTrue(emp_data["hideEmail"])

        employments = Employment.query.filter(
            Employment.company_id == self.company.id,
            Employment.user_id.in_(user_ids),
            Employment.validation_status
            == EmploymentRequestValidationStatus.PENDING,
        ).all()
        self.assertEqual(len(employments), 2)
        for emp in employments:
            self.assertTrue(emp.hide_email)
            self.assertIsNone(emp.email)

    def test_batch_invite_mixed_emails_and_ids(self):
        mails = ["mixed@test.com"]
        user_ids = [self.employee_1.id]
        response = batch_invite(
            self.admin,
            self.company.id,
            mails=mails,
            user_ids=user_ids,
        )

        result = self._get_result(response)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)

    def test_batch_invite_invalid_user_id_ignored(self):
        invalid_id = 999999
        valid_id = self.employee_1.id
        response = batch_invite(
            self.admin,
            self.company.id,
            user_ids=[valid_id, invalid_id],
        )

        result = self._get_result(response)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["userId"], valid_id)

    def test_batch_invite_exceeds_max_size(self):
        extra_users = [UserFactory.create() for _ in range(51)]
        mails = [f"user{i}@test.com" for i in range(50)]
        user_ids = [u.id for u in extra_users]
        response = batch_invite(
            self.admin,
            self.company.id,
            mails=mails,
            user_ids=user_ids,
        )

        self.assertIsNotNone(response.json.get("errors"))

    def test_batch_invite_empty_lists_error(self):
        response = batch_invite(
            self.admin, self.company.id, mails=[], user_ids=[]
        )

        self.assertIsNotNone(response.json.get("errors"))

    def test_batch_invite_unauthorized_user(self):
        non_admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=False
        )
        response = batch_invite(
            non_admin,
            self.company.id,
            mails=["test@test.com"],
        )

        self.assertIsNotNone(response.json.get("errors"))

    def test_batch_invite_other_company(self):
        other_company = CompanyFactory.create()
        other_admin = UserFactory.create(
            post__company=other_company, post__has_admin_rights=True
        )
        response = batch_invite(
            other_admin,
            self.company.id,
            user_ids=[self.employee_1.id],
        )

        self.assertIsNotNone(response.json.get("errors"))

    def test_batch_invite_backward_compatible_mails_only(self):
        """Verify the mutation still works with mails-only (backward compat)."""
        mails = ["compat@test.com"]
        response = batch_invite(self.admin, self.company.id, mails=mails)

        result = self._get_result(response)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)

    def test_batch_invite_duplicate_user_ids_deduplicated(self):
        """Duplicate user IDs should create only one employment."""
        user_id = self.employee_1.id
        response = batch_invite(
            self.admin,
            self.company.id,
            user_ids=[user_id, user_id, user_id],
        )

        result = self._get_result(response)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)

    def test_batch_invite_email_and_id_same_user_no_duplicate(self):
        """Email + user ID for same user should create only one employment."""
        user = self.employee_1
        response = batch_invite(
            self.admin,
            self.company.id,
            mails=[user.email],
            user_ids=[user.id],
        )

        result = self._get_result(response)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
