from datetime import datetime

from app import db
from app.domain.user import HIDDEN_EMAIL
from app.models import Employment
from app.tests import BaseTest
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
)
from app.seed import UserFactory, CompanyFactory


class TestEmployment(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.user_primary_admin = UserFactory.create(
            first_name="Tim",
            last_name="Leader",
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.primary_admin_employment_id = self.user_primary_admin.employments[
            0
        ].id
        self.user_secondary_admin = UserFactory.create(
            first_name="Tim",
            last_name="Leader",
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.secondary_admin_employment_id = (
            self.user_secondary_admin.employments[0].id
        )
        self.user_worker = UserFactory.create(
            first_name="Tim",
            last_name="Worker",
            post__company=self.company,
            post__has_admin_rights=False,
        )
        self.worker_employment_id = self.user_worker.employments[0].id

    def get_admined_employments(self, admin_id):
        return make_authenticated_request(
            time=datetime.now(),
            submitter_id=admin_id,
            query=ApiRequests.admined_companies_employments,
            unexposed_query=False,
            variables={
                "id": admin_id,
            },
        )["data"]["user"]["adminedCompanies"][0]["employments"]

    def test_change_role_to_admin(self, time=datetime(2020, 2, 7, 6)):
        worker_employment = Employment.query.get(self.worker_employment_id)
        self.assertFalse(worker_employment.has_admin_rights)
        make_authenticated_request(
            time=time,
            submitter_id=self.user_primary_admin.id,
            query=ApiRequests.change_employee_role,
            variables={
                "employment_id": self.worker_employment_id,
                "has_admin_rights": True,
            },
        )
        worker_employment = Employment.query.get(self.worker_employment_id)
        self.assertTrue(worker_employment.has_admin_rights)

    def test_change_role_to_worker(self, time=datetime(2020, 2, 7, 6)):
        worker_employment = Employment.query.get(
            self.secondary_admin_employment_id
        )
        self.assertTrue(worker_employment.has_admin_rights)
        make_authenticated_request(
            time=time,
            submitter_id=self.user_primary_admin.id,
            query=ApiRequests.change_employee_role,
            variables={
                "employment_id": self.worker_employment_id,
                "has_admin_rights": False,
            },
        )
        worker_employment = Employment.query.get(self.worker_employment_id)
        self.assertFalse(worker_employment.has_admin_rights)

    def test_change_own_role(self, time=datetime(2020, 2, 7, 6)):
        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_primary_admin.id,
            query=ApiRequests.change_employee_role,
            variables={
                "employment_id": self.primary_admin_employment_id,
                "has_admin_rights": False,
            },
        )
        self.assertEqual(
            response["errors"][0]["extensions"]["code"],
            "USER_SELF_CHANGE_ROLE",
        )

    def test_change_role_with_not_admin(self, time=datetime(2020, 2, 7, 6)):
        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_worker.id,
            query=ApiRequests.change_employee_role,
            variables={
                "employment_id": self.primary_admin_employment_id,
                "has_admin_rights": False,
            },
        )
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "AUTHORIZATION_ERROR"
        )

    def test_terminate_own_employment(self, time=datetime(2020, 2, 7, 6)):
        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_primary_admin.id,
            query=ApiRequests.terminate_employment,
            variables={
                "employment_id": self.primary_admin_employment_id,
                "end_date": "2020-02-07",
            },
        )
        self.assertEqual(
            response["errors"][0]["extensions"]["code"],
            "USER_SELF_TERMINATE_EMPLOYMENT",
        )

    def test_terminate_employment_for_worker(
        self, time=datetime(2020, 2, 7, 6)
    ):
        worker_employment = Employment.query.get(
            self.secondary_admin_employment_id
        )
        self.assertIsNone(worker_employment.end_date)
        make_authenticated_request(
            time=time,
            submitter_id=self.user_primary_admin.id,
            query=ApiRequests.terminate_employment,
            variables={
                "employment_id": self.worker_employment_id,
                "end_date": "2020-02-07",
            },
        )
        worker_employment = Employment.query.get(self.worker_employment_id)
        self.assertIsNotNone(worker_employment.end_date)

    def test_email_is_visible_if_hide_email_is_false(self):
        worker_employment = Employment.query.get(self.worker_employment_id)
        self.assertFalse(worker_employment.hide_email)

        query_employments = self.get_admined_employments(
            self.user_primary_admin.id
        )
        worker_employment = [
            e
            for e in query_employments
            if e["id"] == self.worker_employment_id
        ][0]

        self.assertEqual(
            worker_employment["user"]["email"], self.user_worker.email
        )

    def test_email_is_hidden_if_hide_email_is_true(
        self, time=datetime(2020, 2, 7, 6)
    ):
        worker_employment = Employment.query.get(self.worker_employment_id)
        worker_employment.hide_email = True
        db.session.commit()

        query_employments = self.get_admined_employments(
            self.user_primary_admin.id
        )
        worker_employment = [
            e
            for e in query_employments
            if e["id"] == self.worker_employment_id
        ][0]

        self.assertEqual(worker_employment["user"]["email"], HIDDEN_EMAIL)


class TestReattachEmployment(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.user_admin = UserFactory.create(
            first_name="Admin",
            last_name="User",
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.user_worker = UserFactory.create(
            first_name="Worker",
            last_name="User",
            post__company=self.company,
            post__has_admin_rights=False,
        )
        self.worker_employment = self.user_worker.employments[0]

    def test_reattach_terminated_employment(
        self, time=datetime(2020, 2, 7, 6)
    ):
        from datetime import date

        # Terminate the employment first
        self.worker_employment.end_date = date(2020, 2, 1)
        db.session.commit()

        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_admin.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.user_worker.id,
                "companyId": self.company.id,
            },
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["employments"]["reattachEmployment"]
        new_employment = result["employment"]
        self.assertTrue(result["emailSent"])
        self.assertIsNone(new_employment["endDate"])
        self.assertEqual(new_employment["validationStatus"], "approved")
        self.assertFalse(new_employment["hasAdminRights"])

    def test_reattach_preserves_admin_rights(
        self, time=datetime(2020, 2, 7, 6)
    ):
        from datetime import date

        # Give admin rights then terminate
        self.worker_employment.has_admin_rights = True
        self.worker_employment.end_date = date(2020, 2, 1)
        db.session.commit()

        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_admin.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.user_worker.id,
                "companyId": self.company.id,
            },
        )

        self.assertIsNone(response.get("errors"))
        new_employment = response["data"]["employments"]["reattachEmployment"][
            "employment"
        ]
        self.assertTrue(new_employment["hasAdminRights"])

    def test_reattach_fails_for_non_admin(self, time=datetime(2020, 2, 7, 6)):
        from datetime import date

        other_worker = UserFactory.create(
            first_name="Other",
            last_name="Worker",
            post__company=self.company,
            post__has_admin_rights=False,
        )
        self.worker_employment.end_date = date(2020, 2, 1)
        db.session.commit()

        response = make_authenticated_request(
            time=time,
            submitter_id=other_worker.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.user_worker.id,
                "companyId": self.company.id,
            },
        )

        self.assertIsNotNone(response.get("errors"))
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "AUTHORIZATION_ERROR"
        )

    def test_reattach_fails_when_no_terminated_employment(
        self, time=datetime(2020, 2, 7, 6)
    ):
        # Employment is still active (no end_date)
        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_admin.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.user_worker.id,
                "companyId": self.company.id,
            },
        )

        self.assertIsNotNone(response.get("errors"))
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "INVALID_INPUTS"
        )

    def test_reattach_fails_when_active_employment_exists(
        self, time=datetime(2020, 2, 7, 6)
    ):
        from datetime import date
        from app.models.employment import EmploymentRequestValidationStatus

        # Terminate existing employment, then reattach, then try again
        self.worker_employment.end_date = date(2020, 1, 15)
        db.session.commit()

        # First reattach should work
        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_admin.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.user_worker.id,
                "companyId": self.company.id,
            },
        )
        self.assertIsNone(response.get("errors"))

        # Second reattach should fail - active employment now exists
        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_admin.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.user_worker.id,
                "companyId": self.company.id,
            },
        )

        self.assertIsNotNone(response.get("errors"))
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "INVALID_INPUTS"
        )

    def test_reattach_same_day_cancels_termination(
        self, time=datetime(2020, 2, 7, 6)
    ):
        from datetime import date

        # Terminate the employment on the same day as the reattach request
        # The test runs at 2020-02-07, so we set end_date to 2020-02-07
        same_day = date(2020, 2, 7)
        self.worker_employment.end_date = same_day
        original_employment_id = self.worker_employment.id
        db.session.commit()

        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_admin.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.user_worker.id,
                "companyId": self.company.id,
            },
        )

        self.assertIsNone(response.get("errors"))
        reattached_employment = response["data"]["employments"][
            "reattachEmployment"
        ]["employment"]

        # Same-day reattach should cancel termination, not create new employment
        self.assertEqual(reattached_employment["id"], original_employment_id)
        self.assertIsNone(reattached_employment["endDate"])
        self.assertEqual(reattached_employment["validationStatus"], "approved")

    def test_reattach_dismissed_employment(self, time=datetime(2020, 2, 7, 6)):
        """Test reattaching a dismissed (not terminated) employment."""
        # Dismiss the employment (not terminate with end_date)
        self.worker_employment.dismissed_at = datetime(2020, 2, 1)
        self.worker_employment.dismiss_author_id = self.user_admin.id
        original_employment_id = self.worker_employment.id
        db.session.commit()

        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_admin.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.user_worker.id,
                "companyId": self.company.id,
            },
        )

        self.assertIsNone(response.get("errors"))
        result = response["data"]["employments"]["reattachEmployment"]
        reattached_employment = result["employment"]

        # Dismissed employment should be reactivated, not create new
        self.assertEqual(reattached_employment["id"], original_employment_id)
        self.assertIsNone(reattached_employment["endDate"])
        self.assertEqual(reattached_employment["validationStatus"], "approved")
        self.assertTrue(result["emailSent"])

        # Verify dismissed_at was cleared in DB
        refreshed_employment = Employment.query.get(original_employment_id)
        self.assertIsNone(refreshed_employment.dismissed_at)
        self.assertIsNone(refreshed_employment.dismiss_author_id)

    def test_reattach_preserves_team_id(self, time=datetime(2020, 2, 7, 6)):
        """Test that team_id is preserved when reattaching terminated employment."""
        from datetime import date
        from app.models.team import Team

        # Create a team and assign the worker to it
        team = Team(name="Test Team", company_id=self.company.id)
        db.session.add(team)
        db.session.flush()

        self.worker_employment.team_id = team.id
        self.worker_employment.end_date = date(2020, 2, 1)
        db.session.commit()

        response = make_authenticated_request(
            time=time,
            submitter_id=self.user_admin.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.user_worker.id,
                "companyId": self.company.id,
            },
        )

        self.assertIsNone(response.get("errors"))
        new_employment = response["data"]["employments"]["reattachEmployment"][
            "employment"
        ]

        # team_id should be preserved from terminated employment
        self.assertEqual(new_employment["teamId"], team.id)


class TestEmploymentStatusProperties(BaseTest):
    """Tests for is_active, is_terminated, is_inactive, and status hybrid properties."""

    def setUp(self):
        super().setUp()
        from datetime import date, timedelta
        from app.models.employment import EmploymentRequestValidationStatus

        self.company = CompanyFactory.create()
        self.user_admin = UserFactory.create(
            first_name="Admin",
            last_name="User",
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.user_worker = UserFactory.create(
            first_name="Worker",
            last_name="User",
            post__company=self.company,
            post__has_admin_rights=False,
        )
        self.employment = self.user_worker.employments[0]

    def test_active_employment_status(self):
        """An approved employment with no end_date should be ACTIVE."""
        self.assertTrue(self.employment.is_active)
        self.assertFalse(self.employment.is_terminated)
        self.assertFalse(self.employment.is_inactive)
        self.assertEqual(self.employment.status, "ACTIVE")

    def test_terminated_employment_status(self):
        """An employment with end_date in the past should be TERMINATED."""
        from datetime import date, timedelta

        self.employment.end_date = date.today() - timedelta(days=1)
        db.session.commit()

        self.assertFalse(self.employment.is_active)
        self.assertTrue(self.employment.is_terminated)
        self.assertFalse(self.employment.is_inactive)
        self.assertEqual(self.employment.status, "TERMINATED")

    def test_dismissed_employment_status(self):
        """A dismissed employment should have DISMISSED status."""
        self.employment.dismissed_at = datetime.now()
        self.employment.dismiss_author_id = self.user_admin.id
        db.session.commit()

        self.assertFalse(self.employment.is_active)
        self.assertFalse(self.employment.is_terminated)
        self.assertEqual(self.employment.status, "DISMISSED")

    def test_pending_employment_status(self):
        """A pending employment should have PENDING status."""
        from app.models.employment import EmploymentRequestValidationStatus

        self.employment.validation_status = (
            EmploymentRequestValidationStatus.PENDING
        )
        db.session.commit()

        self.assertFalse(self.employment.is_active)
        self.assertEqual(self.employment.status, "PENDING")

    def test_rejected_employment_status(self):
        """A rejected employment should have REJECTED status."""
        from app.models.employment import EmploymentRequestValidationStatus

        self.employment.validation_status = (
            EmploymentRequestValidationStatus.REJECTED
        )
        db.session.commit()

        self.assertFalse(self.employment.is_active)
        self.assertEqual(self.employment.status, "REJECTED")

    def test_inactive_employment_status(self):
        """An employment with no activity for 3+ months should be INACTIVE."""
        from datetime import timedelta

        # Set last_active_at to more than 90 days ago
        self.employment.last_active_at = datetime.now() - timedelta(days=91)
        db.session.commit()

        self.assertTrue(self.employment.is_active)
        self.assertTrue(self.employment.is_inactive)
        self.assertEqual(self.employment.status, "INACTIVE")

    def test_active_with_recent_activity(self):
        """An employment with recent activity should be ACTIVE, not INACTIVE."""
        from datetime import timedelta

        self.employment.last_active_at = datetime.now() - timedelta(days=30)
        db.session.commit()

        self.assertTrue(self.employment.is_active)
        self.assertFalse(self.employment.is_inactive)
        self.assertEqual(self.employment.status, "ACTIVE")

    def test_employment_ending_today_is_still_active(self):
        """An employment with end_date = today should still be active."""
        from datetime import date

        self.employment.end_date = date.today()
        db.session.commit()

        self.assertTrue(self.employment.is_active)
        self.assertFalse(self.employment.is_terminated)
        self.assertEqual(self.employment.status, "ACTIVE")
