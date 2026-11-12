from datetime import date, timedelta

from app import db
from app.seed import CompanyFactory, UserFactory
from app.tests import BaseTest, test_post_graphql
from app.models.employment import (
    Employment,
    EmploymentRequestValidationStatus,
)


BATCH_INVITE_MUTATION = """
    mutation (
        $companyId: Int!,
        $mails: [Email],
        $userIds: [Int],
        $entries: [EmploymentInviteInput]
    ) {
        employments {
            batchCreateWorkerEmployments(
                companyId: $companyId,
                mails: $mails,
                userIds: $userIds,
                entries: $entries
            ) {
                id
                userId
                email
                isTemporary
                endDate
                hasAdminRights
                hideEmail
            }
        }
    }
"""


def batch_invite(admin, company_id, mails=None, user_ids=None, entries=None):
    variables = {"companyId": company_id}
    if mails is not None:
        variables["mails"] = mails
    if user_ids is not None:
        variables["userIds"] = user_ids
    if entries is not None:
        variables["entries"] = entries
    return test_post_graphql(
        BATCH_INVITE_MUTATION,
        mock_authentication_with_user=admin,
        variables=variables,
    )


class TestBatchInvite(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create(allow_temporary_employees=True)
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.employee_1 = UserFactory.create()
        self.employee_2 = UserFactory.create()
        self.future = date.today() + timedelta(days=30)

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

    def test_mixed_permanent_temporary_admin(self):
        user = UserFactory.create()
        response = batch_invite(
            self.admin,
            self.company.id,
            entries=[
                {"mail": "perm@test.com"},
                {
                    "mail": "temp@test.com",
                    "isTemporary": True,
                    "endDate": str(self.future),
                },
                {"userId": user.id, "hasAdminRights": True},
            ],
        )
        result = self._get_result(response)
        self.assertEqual(len(result), 3)
        by_email = {r["email"]: r for r in result if r["email"]}
        self.assertFalse(by_email["perm@test.com"]["isTemporary"])
        self.assertTrue(by_email["temp@test.com"]["isTemporary"])
        self.assertEqual(
            by_email["temp@test.com"]["endDate"], str(self.future)
        )

    def test_temporary_disabled_nothing_created(self):
        company_id = self.company.id
        self.company.allow_temporary_employees = False
        db.session.commit()
        response = batch_invite(
            self.admin,
            company_id,
            entries=[
                {"mail": "perm@test.com"},
                {
                    "mail": "temp@test.com",
                    "isTemporary": True,
                    "endDate": str(self.future),
                },
            ],
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertIn("not enabled", errors[0]["message"].lower())
        pending = Employment.query.filter_by(
            company_id=company_id,
            validation_status=EmploymentRequestValidationStatus.PENDING,
        ).count()
        self.assertEqual(pending, 0)

    def test_temporary_without_end_date_error(self):
        response = batch_invite(
            self.admin,
            self.company.id,
            entries=[{"mail": "t@test.com", "isTemporary": True}],
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertIn("end date", errors[0]["message"].lower())

    def test_temporary_past_end_date_error(self):
        past = date.today() - timedelta(days=1)
        response = batch_invite(
            self.admin,
            self.company.id,
            entries=[
                {
                    "mail": "t@test.com",
                    "isTemporary": True,
                    "endDate": str(past),
                }
            ],
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertIn("today or later", errors[0]["message"].lower())

    def test_temporary_with_admin_rights_error(self):
        response = batch_invite(
            self.admin,
            self.company.id,
            entries=[
                {
                    "mail": "t@test.com",
                    "isTemporary": True,
                    "endDate": str(self.future),
                    "hasAdminRights": True,
                }
            ],
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertIn("admin rights", errors[0]["message"].lower())

    def test_permanent_with_end_date_error(self):
        response = batch_invite(
            self.admin,
            self.company.id,
            entries=[{"mail": "p@test.com", "endDate": str(self.future)}],
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertIn(
            "only allowed for temporary", errors[0]["message"].lower()
        )

    def test_conflicting_duplicate_error(self):
        response = batch_invite(
            self.admin,
            self.company.id,
            entries=[
                {"mail": "dup@test.com"},
                {
                    "mail": "dup@test.com",
                    "isTemporary": True,
                    "endDate": str(self.future),
                },
            ],
        )
        errors = response.json.get("errors")
        self.assertIsNotNone(errors)
        self.assertIn("conflicting", errors[0]["message"].lower())

    def test_identical_duplicate_merged(self):
        response = batch_invite(
            self.admin,
            self.company.id,
            entries=[{"mail": "dup@test.com"}, {"mail": "dup@test.com"}],
        )
        result = self._get_result(response)
        self.assertEqual(len(result), 1)

    def test_email_of_already_attached_user_no_crash(self):
        existing = UserFactory.create(post__company=self.company)
        response = batch_invite(
            self.admin,
            self.company.id,
            mails=[existing.email],
        )
        self.assertIsNone(response.json.get("errors"))
