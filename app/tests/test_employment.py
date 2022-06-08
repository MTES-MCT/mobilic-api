from datetime import datetime

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
