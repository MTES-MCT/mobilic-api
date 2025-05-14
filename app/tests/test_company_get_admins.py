from datetime import date, datetime, timedelta
from flask import g
from flask.ctx import AppContext

from app import app
from app.models.employment import EmploymentRequestValidationStatus
from app.seed import (
    CompanyFactory,
)
from app.seed.factories import EmploymentFactory, UserFactory
from app.tests import BaseTest


class TestCompanyGetAdmins(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.start = datetime.now()
        self.end = datetime.now()
        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_get_admins_without_users(self):
        admins = self.company.get_admins(self.start, self.end)
        self.assertEqual(len(admins), 0)

    def test_get_admins_with_no_admin_rights(self):
        EmploymentFactory.create(company=self.company, has_admin_rights=False)
        admins = self.company.get_admins(self.start, self.end)
        self.assertEqual(len(admins), 0)

    def test_get_admins_with_dismissed_admin(self):
        admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        EmploymentFactory.create(
            company=self.company,
            has_admin_rights=True,
            dismissed_at=datetime.now(),
            dismiss_author=admin,
        )
        admins = self.company.get_admins(self.start, self.end)
        self.assertEqual(len(admins), 1)
        self.assertEqual(admins[0].id, admin.id)

    def test_get_admins_with_rejected_admin(self):
        EmploymentFactory.create(
            company=self.company,
            has_admin_rights=True,
            validation_status=EmploymentRequestValidationStatus.REJECTED,
        )
        admins = self.company.get_admins(self.start, self.end)
        self.assertEqual(len(admins), 0)

    def test_get_admins_with_past_admin(self):
        yesterday = date.today() - timedelta(days=1)
        EmploymentFactory.create(
            company=self.company,
            has_admin_rights=True,
            end_date=yesterday,
        )
        admins = self.company.get_admins(self.start, self.end)
        self.assertEqual(len(admins), 0)

    def test_get_admins_with_two_admins(self):
        EmploymentFactory.create(company=self.company, has_admin_rights=True)
        EmploymentFactory.create(company=self.company, has_admin_rights=True)
        admins = self.company.get_admins(self.start, self.end)
        self.assertEqual(len(admins), 2)
