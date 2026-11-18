from unittest.mock import patch

from datetime import datetime, timedelta

from app import app, db
from app.jobs import platform_health_check
from app.jobs.platform_health_check import (
    job_purge_healthcheck_bot_missions,
    job_run_platform_health_checks,
    job_send_platform_health_summary,
)
from app.models import (
    Activity,
    Mission,
    PlatformHealthCheckRun,
    RegulationComputation,
)
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
    def test_alert_sent_once_while_failing(self, mock_tchap):
        mock_tchap.return_value = True
        with patch.object(platform_health_check, "EXPECTED_EMPLOYEES", 5):
            job_run_platform_health_checks()
            job_run_platform_health_checks()
        mock_tchap.assert_called_once()
        self.assertEqual(mock_tchap.call_args[0][1], "healthcheck")

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_recovery_message_after_failure(self, mock_tchap):
        mock_tchap.return_value = True
        with patch.object(platform_health_check, "EXPECTED_EMPLOYEES", 5):
            job_run_platform_health_checks()
        job_run_platform_health_checks()
        job_run_platform_health_checks()
        self.assertEqual(mock_tchap.call_count, 2)
        self.assertIn("rétabli", mock_tchap.call_args[0][0])

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_run_recorded_when_alert_delivery_fails(self, mock_tchap):
        mock_tchap.return_value = False
        with patch.object(platform_health_check, "EXPECTED_EMPLOYEES", 5):
            with self.assertRaises(RuntimeError):
                job_run_platform_health_checks()
        run = PlatformHealthCheckRun.query.one()
        self.assertTrue(run.failures)

    def _add_run(self, hours_ago, failures=()):
        db.session.add(
            PlatformHealthCheckRun(
                creation_time=datetime.now() - timedelta(hours=hours_ago),
                failures=[list(failure) for failure in failures],
            )
        )
        db.session.commit()

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_summary_when_everything_works(self, mock_tchap):
        mock_tchap.return_value = True
        for hours_ago in (3, 2, 1):
            self._add_run(hours_ago)
        job_send_platform_health_summary()
        message = mock_tchap.call_args[0][0]
        self.assertIn("✅", message)
        self.assertIn("3/3", message)
        self.assertEqual(mock_tchap.call_args[0][1], "healthcheck")

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_summary_lists_interruptions(self, mock_tchap):
        mock_tchap.return_value = True
        self._add_run(30, [("Ancienne panne", "x")])
        self._add_run(5)
        self._add_run(4, [("Exports KO", "x")])
        self._add_run(3, [("Exports KO", "x"), ("Gestionnaire KO", "y")])
        self._add_run(2)
        self._add_run(1, [("Saisie KO", "z")])
        job_send_platform_health_summary()
        message = mock_tchap.call_args[0][0]
        self.assertIn("2 interruption(s)", message)
        self.assertIn("2/5", message)
        self.assertIn("Exports KO, Gestionnaire KO", message)
        self.assertIn("Saisie KO", message)
        self.assertNotIn("Ancienne panne", message)

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_summary_without_runs(self, mock_tchap):
        mock_tchap.return_value = True
        self._add_run(30)
        job_send_platform_health_summary()
        self.assertIn("aucun passage", mock_tchap.call_args[0][0])

    @patch("app.jobs.platform_health_check.send_tchap_message")
    def test_old_runs_are_purged(self, mock_tchap):
        self._add_run(24 * 8)
        self._add_run(1)
        job_purge_healthcheck_bot_missions()
        self.assertEqual(PlatformHealthCheckRun.query.count(), 1)

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
