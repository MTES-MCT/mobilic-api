from datetime import date, datetime, timedelta
from uuid import uuid4

from app import db
from app.models.employment import Employment, EmploymentRequestValidationStatus
from app.tests import BaseTest, test_post_graphql_unexposed
from app.tests.helpers import make_authenticated_request, ApiRequests
from app.seed import UserFactory, CompanyFactory, EmploymentFactory


QUERY_INVITATION = """
    query ($token: String!) {
        employment(token: $token) {
            id
        }
    }
"""


class TestExpiredInvitation(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create(allow_temporary_employees=True)
        self.admin = UserFactory.create(
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.yesterday = date.today() - timedelta(days=1)
        self.in_ten_days = date.today() + timedelta(days=10)

    def _create_invitation(
        self, end_date, user=None, email=None, is_temporary=True
    ):
        return EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=user,
            email=email or (user.email if user else None),
            invite_token=uuid4().hex,
            is_temporary=is_temporary,
            end_date=end_date,
            validation_status=EmploymentRequestValidationStatus.PENDING,
            validation_time=None,
        )

    def test_validate_expired_invitation_refused(self):
        worker = UserFactory.create()
        emp = self._create_invitation(end_date=self.yesterday, user=worker)

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=worker.id,
            query=ApiRequests.validate_employment,
            variables={"employment_id": emp.id},
        )
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "INVALID_INPUTS"
        )
        self.assertIn("expired", response["errors"][0]["message"].lower())
        emp_db = Employment.query.get(emp.id)
        self.assertEqual(
            emp_db.validation_status,
            EmploymentRequestValidationStatus.PENDING,
        )

    def test_validate_non_expired_invitation_accepted(self):
        worker = UserFactory.create()
        emp = self._create_invitation(end_date=self.in_ten_days, user=worker)

        make_authenticated_request(
            time=datetime.now(),
            submitter_id=worker.id,
            query=ApiRequests.validate_employment,
            variables={"employment_id": emp.id},
        )
        emp_db = Employment.query.get(emp.id)
        self.assertEqual(
            emp_db.validation_status,
            EmploymentRequestValidationStatus.APPROVED,
        )

    def test_redeem_expired_invitation_refused(self):
        worker = UserFactory.create()
        emp = self._create_invitation(end_date=self.yesterday, user=worker)

        response = test_post_graphql_unexposed(
            query=ApiRequests.redeem_invite,
            mock_authentication_with_user=worker,
            variables={"token": emp.invite_token},
        )
        errors = response.json.get("errors")
        self.assertEqual(errors[0]["extensions"]["code"], "EXPIRED_TOKEN")

    def test_signup_with_expired_token_creates_user_but_not_employment(self):
        emp = self._create_invitation(
            end_date=self.yesterday, email="newuser@test.com"
        )
        token = emp.invite_token

        response = test_post_graphql_unexposed(
            query=ApiRequests.create_account,
            variables={
                "email": "newuser@test.com",
                "password": "Passw0rd!Strong",
                "firstName": "New",
                "lastName": "User",
                "inviteToken": token,
            },
        )
        data = response.json
        self.assertNotIn("errors", data)
        self.assertIsNotNone(data["data"]["signUp"]["user"]["accessToken"])

        db.session.rollback()
        emp_db = Employment.query.get(emp.id)
        self.assertEqual(
            emp_db.validation_status,
            EmploymentRequestValidationStatus.PENDING,
        )

    def test_validate_permanent_with_past_end_date_accepted(self):
        worker = UserFactory.create()
        emp = self._create_invitation(
            end_date=self.yesterday, user=worker, is_temporary=False
        )

        make_authenticated_request(
            time=datetime.now(),
            submitter_id=worker.id,
            query=ApiRequests.validate_employment,
            variables={"employment_id": emp.id},
        )
        emp_db = Employment.query.get(emp.id)
        self.assertEqual(
            emp_db.validation_status,
            EmploymentRequestValidationStatus.APPROVED,
        )

    def test_reminder_skipped_for_expired_temporary_invitation(self):
        emp = self._create_invitation(
            end_date=self.yesterday, email="expired@test.com"
        )

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.send_invite_reminder,
            variables={"employment_ids": [emp.id]},
        )
        sent_ids = response["data"]["employments"]["sendInvitationsReminders"][
            "sentToEmploymentIds"
        ]
        self.assertEqual(sent_ids, [])

    def test_query_invitation_expired_returns_expired_token(self):
        emp = self._create_invitation(
            end_date=self.yesterday, email="query@test.com"
        )

        response = test_post_graphql_unexposed(
            query=QUERY_INVITATION,
            variables={"token": emp.invite_token},
        )
        errors = response.json.get("errors")
        self.assertEqual(errors[0]["extensions"]["code"], "EXPIRED_TOKEN")

    def test_query_invitation_non_expired_succeeds(self):
        emp = self._create_invitation(
            end_date=self.in_ten_days, email="query@test.com"
        )

        response = test_post_graphql_unexposed(
            query=QUERY_INVITATION,
            variables={"token": emp.invite_token},
        )
        data = response.json
        self.assertNotIn("errors", data)
        self.assertEqual(data["data"]["employment"]["id"], emp.id)
