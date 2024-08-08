import datetime

from flask.ctx import AppContext

from app import app, db
from app.jobs.emails.cgu.send_email_to_last_company_suspended_admins import (
    get_last_admins_and_blacklist_expiring_users,
)
from app.jobs.emails.cgu.send_expiry_warning_email import (
    get_users_expiring_soon,
    DELAY_HOURS,
)
from app.models import UserAgreement
from app.models.user_agreement import UserAgreementStatus
from app.seed import UserFactory, CompanyFactory, EmploymentFactory
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests

PASSWORD = "password"
EMAIL = "user@email.com"


class TestCGU(BaseTest):
    def setUp(self):
        super().setUp()

        company = CompanyFactory.create(
            usual_name="Company Name", siren="1122334", allow_transfers=True
        )

        user = UserFactory.create(
            email=EMAIL,
            password=PASSWORD,
            first_name="Admin",
            last_name="Admin",
        )
        EmploymentFactory.create(
            company=company, submitter=user, user=user, has_admin_rights=True
        )

        self.user = user
        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _query_cgu_status(self):
        return (
            make_authenticated_request(
                time=datetime.datetime.now(),
                submitter_id=self.user.id,
                query=ApiRequests.query_user_cgu_status,
                variables={"user_id": self.user.id},
            )
            .get("data")
            .get("user")
            .get("userAgreementStatus")
        )

    def _login(self):
        make_authenticated_request(
            time=datetime.datetime.now(),
            submitter_id=self.user.id,
            query=ApiRequests.login_query,
            variables={"email": EMAIL, "password": PASSWORD},
        )

    def test_init_cgu(self):
        user_agreement = UserAgreement.get_or_create(user_id=self.user.id)

        self.assertFalse(user_agreement.is_blacklisted)
        self.assertEqual(user_agreement.status, UserAgreementStatus.PENDING)
        self.assertIsNone(user_agreement.expires_at)
        self.assertFalse(UserAgreement.is_user_blacklisted(self.user.id))

    def test_accept_reject_cgu(self):
        user_agreement = UserAgreement.get_or_create(user_id=self.user.id)

        user_agreement.accept()
        self.assertEqual(user_agreement.status, UserAgreementStatus.ACCEPTED)

        user_agreement.reject()
        self.assertEqual(user_agreement.status, UserAgreementStatus.REJECTED)

        user_agreement.accept()
        self.assertEqual(user_agreement.status, UserAgreementStatus.ACCEPTED)

    def test_cgu_output(self):
        user_agreement = UserAgreement.get_or_create(user_id=self.user.id)

        res = self._query_cgu_status()
        self.assertTrue(res.get("shouldAcceptCgu"))
        self.assertFalse(res.get("hasRejectedCgu"))
        self.assertFalse(res.get("hasAcceptedCgu"))

        user_agreement.accept()
        db.session.add(user_agreement)
        res = self._query_cgu_status()
        self.assertFalse(res.get("shouldAcceptCgu"))
        self.assertFalse(res.get("hasRejectedCgu"))
        self.assertTrue(res.get("hasAcceptedCgu"))

        user_agreement.reject()
        db.session.add(user_agreement)
        res = self._query_cgu_status()
        self.assertFalse(res.get("shouldAcceptCgu"))
        self.assertTrue(res.get("hasRejectedCgu"))
        self.assertFalse(res.get("hasAcceptedCgu"))
        self.assertFalse(res.get("isBlacklisted"))

        UserAgreement.blacklist_user(self.user.id)
        res = self._query_cgu_status()
        self.assertTrue(res.get("isBlacklisted"))

    def test_blacklisting_user_removes_employments(self):
        UserAgreement.get_or_create(user_id=self.user.id)
        self.assertEqual(
            len(self.user.active_employments_at(datetime.date.today())), 1
        )

        UserAgreement.blacklist_user(self.user.id)
        self.assertEqual(
            len(self.user.active_employments_at(datetime.date.today())), 0
        )

    def test_trying_to_connect_after_expiry_date_blacklists_user(self):
        user_agreement = UserAgreement.get_or_create(user_id=self.user.id)
        user_agreement.reject()
        db.session.add(user_agreement)
        self.assertFalse(UserAgreement.is_user_blacklisted(self.user.id))

        user_agreement.expires_at = datetime.datetime.combine(
            datetime.datetime.today(),
            datetime.time.min,
        )

        self._login()
        self.assertTrue(UserAgreement.is_user_blacklisted(self.user.id))

    def test_expiry_warning_email_targets(self):
        user_agreement = UserAgreement.get_or_create(user_id=self.user.id)
        user_agreement.reject()
        db.session.add(user_agreement)

        users, _ = get_users_expiring_soon()
        self.assertEqual(len(users), 0)

        user_agreement.expires_at = (
            datetime.datetime.now() + datetime.timedelta(hours=DELAY_HOURS)
        )

        users, _ = get_users_expiring_soon()
        self.assertEqual(len(users), 1)

    def test_last_company_admin_job_blacklists_user(self):
        user_agreement = UserAgreement.get_or_create(user_id=self.user.id)
        user_agreement.reject()
        db.session.add(user_agreement)

        users = get_last_admins_and_blacklist_expiring_users(
            datetime.datetime.now()
        )
        self.assertEqual(len(users), 0)

        user_agreement.expires_at = datetime.datetime.combine(
            datetime.datetime.today(),
            datetime.time.min,
        )

        users = get_last_admins_and_blacklist_expiring_users(
            datetime.datetime.now()
        )
        self.assertEqual(len(users), 1)
        self.assertTrue(UserAgreement.is_user_blacklisted(self.user.id))
