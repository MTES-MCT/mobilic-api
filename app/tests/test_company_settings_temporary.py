from datetime import date, datetime, timedelta

from app.models.employment import EmploymentRequestValidationStatus
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests
from app.seed import UserFactory, CompanyFactory, EmploymentFactory


class TestDisableTemporaryEmployeesSetting(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create(allow_temporary_employees=True)
        self.admin = UserFactory.create(
            post__company=self.company,
            post__has_admin_rights=True,
        )

    def _disable_setting(self, should_fail=False):
        return make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.edit_company_settings,
            variables={
                "company_id": self.company.id,
                "allow_temporary_employees": False,
            },
            unexposed_query=True,
            request_should_fail_with={"status": 200} if should_fail else None,
        )

    def _assert_disable_refused(self, response):
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "INVALID_INPUTS"
        )
        self.assertIn(
            "cannot disable", response["errors"][0]["message"].lower()
        )

    def _assert_disable_allowed(self, response):
        settings = response["data"]["editCompanySettings"]["settings"]
        self.assertFalse(settings["allowTemporaryEmployees"])

    def _create_temporary_employment(self, end_date, **kwargs):
        return EmploymentFactory.create(
            company=self.company,
            is_temporary=True,
            end_date=end_date,
            **kwargs,
        )

    def test_disable_allowed_without_temporary(self):
        response = self._disable_setting()
        self._assert_disable_allowed(response)

    def test_disable_refused_with_end_date_tomorrow(self):
        tomorrow = date.today() + timedelta(days=1)
        self._create_temporary_employment(end_date=tomorrow)

        response = self._disable_setting(should_fail=True)
        self._assert_disable_refused(response)

    def test_disable_refused_with_pending_temporary_invitation(self):
        tomorrow = date.today() + timedelta(days=1)
        self._create_temporary_employment(
            end_date=tomorrow,
            validation_status=EmploymentRequestValidationStatus.PENDING,
            validation_time=None,
        )

        response = self._disable_setting(should_fail=True)
        self._assert_disable_refused(response)

    def test_disable_allowed_with_end_date_today(self):
        today = date.today()
        self._create_temporary_employment(end_date=today)

        response = self._disable_setting()
        self._assert_disable_allowed(response)

    def test_disable_allowed_when_temporary_is_dismissed(self):
        future = date.today() + timedelta(days=30)
        self._create_temporary_employment(
            end_date=future,
            dismissed_at=datetime.now(),
            dismiss_author=self.admin,
        )

        response = self._disable_setting()
        self._assert_disable_allowed(response)

    def test_disable_allowed_when_temporary_is_rejected(self):
        future = date.today() + timedelta(days=30)
        self._create_temporary_employment(
            end_date=future,
            validation_status=EmploymentRequestValidationStatus.REJECTED,
            validation_time=None,
        )

        response = self._disable_setting()
        self._assert_disable_allowed(response)
