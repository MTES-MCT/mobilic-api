from unittest.mock import patch

from datetime import datetime, timedelta

from app import app, db
from app.jobs import platform_health_check
from app.jobs.platform_health_check import (
    job_purge_healthcheck_bot_missions,
    job_run_platform_health_checks,
)
from app.models import Activity, Mission, RegulationComputation
from app.seed import UserFactory, CompanyFactory, EmploymentFactory
from app.tests import BaseTest
from app.tests.healthcheck_http import route_bot_http_to_test_client
from app.tests.helpers import init_businesses_data, init_regulation_checks_data


class TestPlatformHealthCheck(BaseTest):
    def setUp(self):
        super().setUp()
        init_businesses_data()
        init_regulation_checks_data()
        self.company = CompanyFactory.create(
            usual_name="Bot Company", siren="123456789"
        )
        self.bot_user = UserFactory.create(
            email=platform_health_check.BOT_USER_EMAIL
        )
        EmploymentFactory.create(
            company=self.company,
            submitter=self.bot_user,
            user=self.bot_user,
            has_admin_rights=True,
        )
        self.employee = UserFactory.create(email="employee@test.com")
        EmploymentFactory.create(
            company=self.company,
            submitter=self.bot_user,
            user=self.employee,
            has_admin_rights=False,
        )
        self.http_patches = route_bot_http_to_test_client()
        self.http_patches.__enter__()
        self.sleep_patch = patch.object(platform_health_check.time, "sleep")
        self.sleep_patch.start()

    def tearDown(self):
        self.sleep_patch.stop()
        self.http_patches.__exit__(None, None, None)
        super().tearDown()

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_no_alert_when_everything_works(self, mock_tchap):
        job_run_platform_health_checks()
        mock_tchap.assert_not_called()

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_alert_when_employees_missing(self, mock_tchap):
        mock_tchap.return_value = True
        with patch.object(platform_health_check, "EXPECTED_EMPLOYEES", 5):
            job_run_platform_health_checks()
        mock_tchap.assert_called_once()
        message = mock_tchap.call_args[0][0]
        self.assertIn("gestionnaire", message)
        self.assertIn("exports", message)
        self.assertNotIn("Enregistrement", message)

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_alert_when_activity_logging_fails(self, mock_tchap):
        mock_tchap.return_value = True
        with patch.object(
            platform_health_check,
            "check_activity_logging",
            side_effect=Exception("boom"),
        ):
            job_run_platform_health_checks()
        mock_tchap.assert_called_once()
        self.assertIn("Enregistrement", mock_tchap.call_args[0][0])

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_alert_when_api_host_missing(self, mock_tchap):
        mock_tchap.return_value = True
        with patch.dict(app.config, {"API_HOST": None}):
            job_run_platform_health_checks()
        mock_tchap.assert_called_once()
        self.assertIn("API_HOST", mock_tchap.call_args[0][0])

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_bot_missions_are_purged(self, mock_tchap):
        job_run_platform_health_checks()
        mock_tchap.assert_not_called()
        bot_missions = Mission.query.filter(
            Mission.name == platform_health_check.BOT_MISSION_NAME
        )
        self.assertEqual(bot_missions.count(), 1)

        job_purge_healthcheck_bot_missions()
        self.assertEqual(bot_missions.count(), 1)

        Mission.query.filter(
            Mission.name == platform_health_check.BOT_MISSION_NAME
        ).update({Mission.reception_time: datetime.now() - timedelta(days=2)})
        RegulationComputation.query.update(
            {
                RegulationComputation.creation_time: datetime.now()
                - timedelta(days=2)
            }
        )
        db.session.commit()
        self.assertGreater(RegulationComputation.query.count(), 0)
        self.assertEqual(job_purge_healthcheck_bot_missions(), 1)
        self.assertEqual(RegulationComputation.query.count(), 0)
        self.assertEqual(bot_missions.count(), 0)
        self.assertEqual(Activity.query.count(), 0)
