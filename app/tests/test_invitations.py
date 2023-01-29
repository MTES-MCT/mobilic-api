import unittest

from app.seed import CompanyFactory, UserFactory
from app.tests import (
    BaseTest,
    test_post_graphql,
    test_post_graphql_unexposed,
)
from app.models import Employment, User
from app.models.employment import EmploymentRequestValidationStatus
from app.tests.helpers import ApiRequests


def get_invite_token(response):
    invitation_id = (
        response.json.get("data")
        .get("employments")
        .get("createEmployment")
        .get("id")
    )
    return Employment.query.filter_by(id=invitation_id).first().invite_token


def create_account_get_user(
    email, password, first_name, last_name, invite_token=None
):
    test_post_graphql_unexposed(
        ApiRequests.create_account,
        variables=dict(
            email=email,
            password=password,
            firstName=first_name,
            lastName=last_name,
            inviteToken=invite_token,
        ),
    )

    return User.query.filter_by(email=email).first()


def invite_user_by_userid(admin, user_id, company):
    return test_post_graphql(
        ApiRequests.invite,
        mock_authentication_with_user=admin,
        variables=dict(userId=user_id, companyId=company.id),
    )


def invite_user_by_email(admin, email, company):
    return test_post_graphql(
        ApiRequests.invite,
        mock_authentication_with_user=admin,
        variables=dict(mail=email, companyId=company.id),
    )


class TestInvitations(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.company2 = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.admin2 = UserFactory.create(
            post__company=self.company2, post__has_admin_rights=True
        )
        self.employee_1 = UserFactory.create()

    def check_has_pending_invite(self, employee, company):
        employments = Employment.query.filter_by(
            user_id=employee.id,
            company_id=company.id,
            validation_status=EmploymentRequestValidationStatus.PENDING,
        ).all()
        self.assertEqual(len(employments), 1)

    def check_has_pending_invite_by_email(self, email, company):
        employments = Employment.query.filter_by(
            email=email,
            company_id=company.id,
            validation_status=EmploymentRequestValidationStatus.PENDING,
        ).all()
        self.assertEqual(len(employments), 1)

    def check_is_working_for(self, employee, company):
        employments = Employment.query.filter_by(
            user_id=employee.id,
            company_id=company.id,
            validation_status=EmploymentRequestValidationStatus.APPROVED,
        ).all()
        self.assertEqual(len(employments), 1)

    def test_invite_new_user_by_email(self):
        new_user_email = "blabla@test.com"

        invite_user_by_email(self.admin, new_user_email, self.company)

        self.check_has_pending_invite_by_email(new_user_email, self.company)

    def test_invite_existing_user_by_userid(self):

        invite_user_by_userid(self.admin, self.employee_1.id, self.company)

        self.check_has_pending_invite(self.employee_1, self.company)

    def test_invite_existing_user_by_email(self):
        invite_user_by_email(self.admin, self.employee_1.email, self.company)

        self.check_has_pending_invite(self.employee_1, self.company)

    def test_invite_existing_user_by_email_case_insensitive(self):
        invite_user_by_email(
            self.admin, self.employee_1.email.upper(), self.company
        )

        self.check_has_pending_invite(self.employee_1, self.company)

    def test_error_when_invite_non_existing_user(self):
        # admin invites an employee who doesn't exist
        invite_response = invite_user_by_userid(
            self.admin, 12545214, self.company
        )

        self.assertIsNotNone(invite_response.json.get("errors"))
        error_messages = [
            err["message"] for err in invite_response.json.get("errors")
        ]
        self.assertIn("Invalid user id", error_messages)

    def test_invite_future_employee_with_token(self):
        future_employee_email = "future_employee@toto.com"

        # admin invites an employee who doesn't exist
        invite_response = invite_user_by_email(
            self.admin, future_employee_email, self.company
        )
        invite_token = get_invite_token(invite_response)

        # new employee creates an account via the invite token
        new_employee = create_account_get_user(
            email=future_employee_email,
            password="greatpassword1@",
            first_name="Albert",
            last_name="Einstein",
            invite_token=invite_token,
        )

        self.check_is_working_for(new_employee, self.company)

    def test_invite_future_employee_with_email(self):
        future_employee_email = "future_employee@titi.com"

        # admin invites an employee who doesn't exist
        invite_user_by_email(self.admin, future_employee_email, self.company)

        # new employee creates an account without using invite token
        new_employee = create_account_get_user(
            email=future_employee_email,
            password="fabulouspassword1@",
            first_name="Magicien",
            last_name="Oz",
        )

        self.check_has_pending_invite(new_employee, self.company)

    # TO BE REMOVED (used only to debug below test)
    def print_employments(self):
        print(f"-----")
        employments = Employment.query.all()
        for e in employments:
            print(
                f"company={e.company_id}, user={e.user_id}, email={e.email}, validation_status={e.validation_status}"
            )

    # FIXME
    @unittest.skip(
        "Unresolved error: another instance with key is already present in this session."
    )
    def test_two_companies_invite_future_employee(self):
        future_employee_email = "future_employee@toto.com"

        # admin invites an employee who doesn't exist
        response = invite_user_by_email(
            self.admin, future_employee_email, self.company
        )
        self.assertTrue(response.status_code, 200)
        self.print_employments()

        # second admin does the same
        response = invite_user_by_email(
            self.admin2, future_employee_email, self.company2
        )
        print(f"{response.json}")
        self.assertTrue(response.status_code, 200)
        self.print_employments()

        # new employee creates an account without using invite token
        new_employee = create_account_get_user(
            email=future_employee_email,
            password="greatpassword",
            first_name="Albert",
            last_name="Einstein",
        )

        # new employee has a pending invite from both companies
        self.check_has_pending_invite(new_employee, self.company)
        self.check_has_pending_invite(new_employee, self.company2)

    def test_invite_by_email_case_insensitive(self):
        future_employee_email = "future_employee@toto.com"

        # admin invites an employee who doesn't exist in UPPER CASE
        invite_user_by_email(
            self.admin, future_employee_email.upper(), self.company
        )

        # new employee creates an account without using invite token
        new_employee = create_account_get_user(
            email=future_employee_email,
            password="greatpassword1@",
            first_name="Albert",
            last_name="Einstein",
        )

        self.check_has_pending_invite(new_employee, self.company)
