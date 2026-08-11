from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app import app, db
from app.models import Mission
from app.models.activity import Activity, ActivityType
from app.seed import UserFactory, CompanyFactory, AuthenticatedUserContext
from app.tests import BaseTest
from app.jobs.break_alert import (
    get_uninterrupted_work_start,
    schedule_break_alert_if_needed,
    send_break_alert_task,
)
from flask.ctx import AppContext


class TestBreakAlert(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.worker = UserFactory.create(post__company=self.company)
        self._ctx = AppContext(app)
        self._ctx.__enter__()
        now = datetime.now()
        self.t0 = now.replace(second=0, microsecond=0) - timedelta(hours=8)
        with AuthenticatedUserContext(user=self.worker):
            self.mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=self.t0,
            )

    def tearDown(self):
        self._ctx.__exit__(None, None, None)
        super().tearDown()

    def _add_activity(self, type_, start, end=None):
        a = Activity(
            type=type_,
            start_time=start,
            end_time=end,
            mission=self.mission,
            user=self.worker,
            submitter=self.worker,
            reception_time=end or start,
            last_update_time=end or start,
        )
        db.session.add(a)
        db.session.flush()
        return a

    def test_continuous_work_chains_back(self):
        t1 = self.t0 + timedelta(hours=2)
        t2 = t1 + timedelta(hours=1)
        self._add_activity(ActivityType.DRIVE, self.t0, t1)
        self._add_activity(ActivityType.WORK, t1, t2)
        db.session.commit()
        result = get_uninterrupted_work_start(self.worker, self.mission, t2)
        self.assertEqual(result, self.t0)

    def test_gap_resets_work_start(self):
        t1 = self.t0 + timedelta(hours=2)
        t2 = t1 + timedelta(minutes=30)
        t3 = t2 + timedelta(hours=1)
        self._add_activity(ActivityType.DRIVE, self.t0, t1)
        self._add_activity(ActivityType.DRIVE, t2, t3)
        db.session.commit()
        result = get_uninterrupted_work_start(self.worker, self.mission, t3)
        self.assertEqual(result, t2)

    @patch("app.jobs.break_alert.send_break_alert_task")
    def test_off_activity_no_alert(self, mock_task):
        a = self._add_activity(ActivityType.OFF, self.t0)
        schedule_break_alert_if_needed(self.worker.id, a, self.t0)
        mock_task.apply_async.assert_not_called()

    @patch("app.jobs.break_alert.send_break_alert_task")
    def test_retroactive_entry_no_alert(self, mock_task):
        past = self.t0 - timedelta(minutes=10)
        a = self._add_activity(ActivityType.DRIVE, past)
        schedule_break_alert_if_needed(self.worker.id, a, self.t0)
        mock_task.apply_async.assert_not_called()

    @patch("app.jobs.break_alert.send_break_alert_task")
    def test_real_time_entry_schedules(self, mock_task):
        a = self._add_activity(ActivityType.DRIVE, self.t0)
        schedule_break_alert_if_needed(self.worker.id, a, self.t0)
        mock_task.apply_async.assert_called_once()

    @patch("app.jobs.break_alert.send_push_notification")
    @patch("app.jobs.break_alert._get_redis")
    def test_sends_if_activity_ongoing(self, mock_redis, mock_push):
        mock_redis.return_value = MagicMock(get=lambda k: None)
        a = self._add_activity(ActivityType.DRIVE, self.t0)
        db.session.commit()
        send_break_alert_task(self.worker.id, a.id, int(self.t0.timestamp()))
        mock_push.assert_called_once()

    @patch("app.jobs.break_alert.send_push_notification")
    @patch("app.jobs.break_alert._get_redis")
    def test_skips_if_activity_ended(self, mock_redis, mock_push):
        mock_redis.return_value = MagicMock(get=lambda k: None)
        a = self._add_activity(
            ActivityType.DRIVE,
            self.t0,
            self.t0 + timedelta(hours=1),
        )
        db.session.commit()
        send_break_alert_task(self.worker.id, a.id, int(self.t0.timestamp()))
        mock_push.assert_not_called()

    @patch("app.jobs.break_alert.send_push_notification")
    @patch("app.jobs.break_alert._get_redis")
    def test_skips_if_already_sent(self, mock_redis, mock_push):
        mock_redis.return_value = MagicMock(get=lambda k: b"1")
        a = self._add_activity(ActivityType.DRIVE, self.t0)
        db.session.commit()
        send_break_alert_task(self.worker.id, a.id, int(self.t0.timestamp()))
        mock_push.assert_not_called()
