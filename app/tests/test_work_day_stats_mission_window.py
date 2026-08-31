from datetime import date, datetime, time, timedelta, timezone

from app.models.activity import ActivityType
from app.models.queries import MISSION_WINDOW_MARGIN_DAYS, query_work_day_stats
from app.seed import CompanyFactory, UserFactory
from app.seed.factories import ActivityFactory, MissionFactory
from app.tests import BaseTest


class TestWorkDayStatsMissionWindow(BaseTest):
    """query_work_day_stats filters missions by creation_time to avoid scanning
    the whole mission table. The margin must never drop an activity that falls
    inside the requested window (Trello 2697)."""

    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.employee = UserFactory.create(post__company=self.company)
        self.today = date(2026, 8, 26)

    def _mission_with_activity(self, activity_day, mission_creation):
        start = datetime.combine(activity_day, time(8, 0), tzinfo=timezone.utc)
        end = start + timedelta(hours=2)
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=self.employee.id,
            reception_time=start,
            creation_time=mission_creation,
        )
        ActivityFactory.create(
            mission=mission,
            user=self.employee,
            submitter=self.employee,
            type=ActivityType.DRIVE,
            reception_time=start,
            start_time=start,
            end_time=end,
            last_update_time=end,
        )
        return mission

    def _worked_user_ids(self, start_date, end_date):
        rows, _ = query_work_day_stats(
            self.company.id, start_date=start_date, end_date=end_date
        )
        return {r.user_id for r in rows if r.service_duration > 0}

    def test_in_window_mission_is_returned(self):
        window_start = self.today - timedelta(days=5)
        self._mission_with_activity(
            activity_day=self.today - timedelta(days=1),
            mission_creation=datetime.combine(
                self.today - timedelta(days=1), time(8, 0), tzinfo=timezone.utc
            ),
        )
        self.assertIn(
            self.employee.id,
            self._worked_user_ids(window_start, self.today),
        )

    def test_activity_kept_when_mission_created_within_margin(self):
        window_start = self.today - timedelta(days=5)
        # Mission created a few days before the window (within the margin) but
        # its activity falls inside the window: it must not be filtered out.
        mission_creation = datetime.combine(
            window_start - timedelta(days=MISSION_WINDOW_MARGIN_DAYS - 1),
            time(8, 0),
            tzinfo=timezone.utc,
        )
        self._mission_with_activity(
            activity_day=self.today - timedelta(days=1),
            mission_creation=mission_creation,
        )
        self.assertIn(
            self.employee.id,
            self._worked_user_ids(window_start, self.today),
        )
