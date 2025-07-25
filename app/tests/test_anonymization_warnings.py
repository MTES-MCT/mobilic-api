import datetime
from unittest.mock import patch
from freezegun import freeze_time

from app import db
from app.jobs.emails.send_anonymization_warnings import (
    send_anonymization_warnings,
    get_anonymization_warning_preview,
)
from app.models import Email
from app.seed import UserFactory, CompanyFactory, EmploymentFactory
from app.tests import BaseTest
from app.helpers.mail_type import EmailType


class TestAnonymizationWarnings(BaseTest):
    def setUp(self):
        super().setUp()

        self.company = CompanyFactory.create(
            usual_name="Test Company", siren="1234567", allow_transfers=True
        )

        self.employee = UserFactory.create(
            email="employee@test.com",
            first_name="Test",
            last_name="Employee",
        )
        EmploymentFactory.create(
            company=self.company,
            submitter=self.employee,
            user=self.employee,
            has_admin_rights=False,
        )

        self.manager = UserFactory.create(
            email="manager@test.com",
            first_name="Test",
            last_name="Manager",
        )
        EmploymentFactory.create(
            company=self.company,
            submitter=self.manager,
            user=self.manager,
            has_admin_rights=True,
        )

    @patch(
        "app.jobs.emails.send_anonymization_warnings.mailer.send_anonymization_warning_employee_email"
    )
    @patch(
        "app.services.anonymization.user_related.classifier.UserClassifier.find_inactive_users"
    )
    @patch(
        "app.services.anonymization.common.AnonymizationManager.calculate_cutoff_date"
    )
    @freeze_time("2025-06-26")
    def test_send_warnings_to_inactive_users(
        self, mock_cutoff_date, mock_classifier, mock_employee_email
    ):
        """Test that warnings are sent to users who will be anonymized in 15 days."""
        mock_cutoff_date.return_value = datetime.datetime(
            2025, 6, 26
        )  # Warning date will be 2025-07-11

        mock_classifier.return_value = {
            "users": [self.employee.id],
            "admins": [],
            "controllers": [],
        }

        results = send_anonymization_warnings()

        mock_employee_email.assert_called_once()
        args = mock_employee_email.call_args[0]
        self.assertEqual(args[0].id, self.employee.id)
        self.assertEqual(args[1], "11/07/2025")  # 15 days from frozen date

        self.assertEqual(results["employees_sent"], 1)
        self.assertEqual(results["managers_sent"], 0)
        self.assertEqual(results["total_sent"], 1)

    @patch(
        "app.jobs.emails.send_anonymization_warnings.mailer.send_anonymization_warning_manager_email"
    )
    @patch(
        "app.services.anonymization.user_related.classifier.UserClassifier.find_inactive_users"
    )
    @patch(
        "app.services.anonymization.common.AnonymizationManager.calculate_cutoff_date"
    )
    @freeze_time("2025-06-26")
    def test_send_warnings_to_inactive_managers(
        self, mock_cutoff_date, mock_classifier, mock_manager_email
    ):
        """Test that warnings are sent to managers who will be anonymized in 15 days."""
        mock_cutoff_date.return_value = datetime.datetime(
            2025, 6, 26
        )  # Warning date will be 2025-07-11

        mock_classifier.return_value = {
            "users": [],
            "admins": [self.manager.id],
            "controllers": [],
        }

        results = send_anonymization_warnings()

        mock_manager_email.assert_called_once()
        args = mock_manager_email.call_args[0]
        self.assertEqual(args[0].id, self.manager.id)
        self.assertEqual(args[1].id, self.company.id)
        self.assertEqual(args[2], "11/07/2025")  # 15 days from frozen date

        self.assertEqual(results["employees_sent"], 0)
        self.assertEqual(results["managers_sent"], 1)
        self.assertEqual(results["total_sent"], 1)

    @patch(
        "app.services.anonymization.user_related.classifier.UserClassifier.find_inactive_users"
    )
    @patch(
        "app.services.anonymization.common.AnonymizationManager.calculate_cutoff_date"
    )
    @freeze_time("2025-06-26")
    def test_no_duplicate_warnings_sent(
        self, mock_cutoff_date, mock_classifier
    ):
        """Test that users already warned in last 14 days don't get warned again."""
        mock_cutoff_date.return_value = datetime.datetime(2025, 6, 26)

        mock_classifier.return_value = {
            "users": [self.employee.id],
            "admins": [],
            "controllers": [],
        }

        recent_warning = Email(
            user_id=self.employee.id,
            type=EmailType.ANONYMIZATION_WARNING_EMPLOYEE,
            mailjet_id="test-mailjet-id-123",
            address=self.employee.email,
            creation_time=datetime.datetime.now() - datetime.timedelta(days=7),
        )
        db.session.add(recent_warning)
        db.session.commit()

        results = send_anonymization_warnings()

        self.assertEqual(results["employees_sent"], 0)
        self.assertEqual(results["managers_sent"], 0)
        self.assertEqual(results["total_sent"], 0)

    @patch(
        "app.services.anonymization.user_related.classifier.UserClassifier.find_inactive_users"
    )
    @patch(
        "app.services.anonymization.common.AnonymizationManager.calculate_cutoff_date"
    )
    @freeze_time("2025-06-26")
    def test_preview_statistics(self, mock_cutoff_date, mock_classifier):
        """Test that preview mode returns correct statistics without sending emails."""
        mock_cutoff_date.return_value = datetime.datetime(2025, 6, 26)

        mock_classifier.return_value = {
            "users": [self.employee.id],
            "admins": [self.manager.id],
            "controllers": [],
        }

        stats = get_anonymization_warning_preview()

        self.assertEqual(stats["target_date"], "11/07/2025")
        self.assertEqual(stats["total_inactive_employees"], 1)
        self.assertEqual(stats["total_inactive_managers"], 1)
        self.assertEqual(stats["employees_to_warn"], 1)
        self.assertEqual(stats["managers_to_warn"], 1)
        self.assertEqual(stats["employees_already_warned"], 0)
        self.assertEqual(stats["managers_already_warned"], 0)

    @patch(
        "app.services.anonymization.user_related.classifier.UserClassifier.find_inactive_users"
    )
    @patch(
        "app.services.anonymization.common.AnonymizationManager.calculate_cutoff_date"
    )
    def test_no_warnings_when_no_inactive_users(
        self, mock_cutoff_date, mock_classifier
    ):
        """Test that no emails are sent when no users are inactive."""
        mock_cutoff_date.return_value = datetime.datetime(2025, 6, 26)

        mock_classifier.return_value = {
            "users": [],
            "admins": [],
            "controllers": [],
        }

        results = send_anonymization_warnings()

        self.assertEqual(results["employees_sent"], 0)
        self.assertEqual(results["managers_sent"], 0)
        self.assertEqual(results["total_sent"], 0)

    @patch(
        "app.services.anonymization.user_related.classifier.UserClassifier.find_inactive_users"
    )
    @patch(
        "app.services.anonymization.common.AnonymizationManager.calculate_cutoff_date"
    )
    def test_skips_users_without_email(
        self, mock_cutoff_date, mock_classifier
    ):
        """Test that users without email addresses are skipped."""
        user_no_email = UserFactory.create(
            email=None,
            first_name="No",
            last_name="Email",
        )
        EmploymentFactory.create(
            company=self.company,
            submitter=user_no_email,
            user=user_no_email,
            has_admin_rights=False,
        )

        mock_cutoff_date.return_value = datetime.datetime(2025, 6, 26)

        mock_classifier.return_value = {
            "users": [user_no_email.id],
            "admins": [],
            "controllers": [],
        }

        results = send_anonymization_warnings()

        self.assertEqual(results["employees_sent"], 0)
        self.assertEqual(results["managers_sent"], 0)
        self.assertEqual(results["total_sent"], 0)
