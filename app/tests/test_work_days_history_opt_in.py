from sqlalchemy import event
from sqlalchemy.engine import Engine

from app import db
from app.domain.work_days import group_user_events_by_day_with_limit
from app.models.activity import ActivityType
from app.seed.helpers import get_date, get_time
from app.tests.regulations import RegulationsTest


class TestWorkDaysHistoryOptIn(RegulationsTest):
    def setUp(self):
        super().setUp()
        self.day = get_date(how_many_days_ago=2)
        self._log_and_validate_mission(
            "Mission history opt-in",
            self.admin,
            [
                (get_time(2, 8), get_time(2, 10), ActivityType.DRIVE),
                (get_time(2, 12), get_time(2, 14), ActivityType.WORK),
            ],
        )

    def _group(self, **kwargs):
        db.session.expire_all()
        return group_user_events_by_day_with_limit(
            self.admin, from_date=self.day, until_date=self.day, **kwargs
        )

    def _missions(self, work_days):
        return [m for wd in work_days for m in wd.missions]

    def test_history_not_computed_by_default(self):
        work_days, _ = self._group()
        missions = self._missions(work_days)
        self.assertTrue(missions)
        for mission in missions:
            self.assertIsNone(getattr(mission, "history", None))

    def test_history_computed_when_requested(self):
        work_days, _ = self._group(compute_history=True)
        missions = self._missions(work_days)
        self.assertTrue(missions)
        for mission in missions:
            self.assertIsNotNone(getattr(mission, "history", None))

    def test_default_emits_fewer_queries_than_history(self):
        counts = []

        def _count(*args, **kwargs):
            counts[-1] += 1

        event.listen(Engine, "before_cursor_execute", _count)
        try:
            counts.append(0)
            self._group()
            n_default = counts[-1]
            counts.append(0)
            self._group(compute_history=True)
            n_history = counts[-1]
        finally:
            event.remove(Engine, "before_cursor_execute", _count)
        self.assertLess(n_default, n_history)

    def test_history_flag_does_not_alter_work_days_output(self):
        default_days, _ = self._group()
        history_days, _ = self._group(compute_history=True)

        self.assertEqual(
            [wd.day for wd in default_days],
            [wd.day for wd in history_days],
        )
        for wd_default, wd_history in zip(default_days, history_days):
            self.assertEqual(
                wd_default.total_work_duration,
                wd_history.total_work_duration,
            )
            self.assertEqual(
                wd_default.service_duration,
                wd_history.service_duration,
            )
            self.assertEqual(
                sorted(a.id for a in wd_default.activities),
                sorted(a.id for a in wd_history.activities),
            )
            self.assertEqual(
                sorted(m.id for m in wd_default.missions),
                sorted(m.id for m in wd_history.missions),
            )
