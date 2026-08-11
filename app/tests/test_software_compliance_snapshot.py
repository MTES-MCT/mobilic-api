from datetime import date, datetime, timedelta

from app import db
from app.helpers.oauth.models import OAuth2Client
from app.jobs.software_compliance_report import (
    MIN_MISSIONS_FOR_ACTIVE_DAY,
    _compute_and_store_snapshots,
    _get_violations,
)
from app.models.activity import ActivityType
from app.models.software_compliance_snapshot import SoftwareComplianceSnapshot
from app.seed.factories import (
    CompanyFactory,
    EmploymentFactory,
    MissionFactory,
    ActivityFactory,
    ThirdPartyClientCompanyFactory,
    UserFactory,
)
from app.tests import BaseTest


SNAPSHOT_DATE = date(2026, 8, 8)
DAY_START = datetime(2026, 8, 8, 0, 0)
DAY_END = datetime(2026, 8, 9, 0, 0)


class TestSoftwareComplianceSnapshot(BaseTest):
    def setUp(self):
        super().setUp()

        self.oauth_client = OAuth2Client.create_client(
            name="test_client", redirect_uris="http://localhost:3000"
        )
        self.company = CompanyFactory.create()
        ThirdPartyClientCompanyFactory.create(
            client=self.oauth_client, company=self.company
        )
        self.user = UserFactory.create()
        EmploymentFactory.create(
            company=self.company,
            user=self.user,
            has_admin_rights=False,
        )

    def _make_mission(self, reception_time):
        return MissionFactory.create(
            company=self.company,
            submitter=self.user,
            reception_time=reception_time,
        )

    def _make_activity(self, mission, start_time, reception_time):
        return ActivityFactory.create(
            mission=mission,
            user=self.user,
            submitter=self.user,
            type=ActivityType.DRIVE,
            start_time=start_time,
            reception_time=reception_time,
            last_update_time=reception_time,
        )

    def _make_snapshots(self, count, **extra):
        for i in range(count):
            db.session.add(
                SoftwareComplianceSnapshot(
                    snapshot_date=date.today() - timedelta(days=i + 1),
                    client_id=self.oauth_client.id,
                    client_name=self.oauth_client.name,
                    nb_missions=MIN_MISSIONS_FOR_ACTIVE_DAY,
                    nb_activities=10,
                    **extra,
                )
            )
        db.session.commit()

    def test_snapshot_created_for_client_with_missions(self):
        mission = self._make_mission(DAY_START + timedelta(hours=9))
        self._make_activity(
            mission,
            start_time=DAY_START + timedelta(hours=8, minutes=55),
            reception_time=DAY_START + timedelta(hours=9),
        )

        _compute_and_store_snapshots(SNAPSHOT_DATE)

        snapshot = SoftwareComplianceSnapshot.query.filter_by(
            client_id=self.oauth_client.id, snapshot_date=SNAPSHOT_DATE
        ).one_or_none()
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.nb_missions, 1)
        self.assertEqual(snapshot.nb_activities, 1)

    def test_no_snapshot_when_no_missions_on_that_day(self):
        _compute_and_store_snapshots(SNAPSHOT_DATE)

        snapshot = SoftwareComplianceSnapshot.query.filter_by(
            client_id=self.oauth_client.id, snapshot_date=SNAPSHOT_DATE
        ).one_or_none()
        self.assertIsNone(snapshot)

    def test_retroactive_activity_detected(self):
        mission = self._make_mission(DAY_START + timedelta(hours=20))
        # 12h delay between start_time and reception_time → >4h retroactive
        self._make_activity(
            mission,
            start_time=DAY_START + timedelta(hours=8),
            reception_time=DAY_START + timedelta(hours=20),
        )

        _compute_and_store_snapshots(SNAPSHOT_DATE)

        snapshot = SoftwareComplianceSnapshot.query.filter_by(
            client_id=self.oauth_client.id, snapshot_date=SNAPSHOT_DATE
        ).one_or_none()
        self.assertIsNotNone(snapshot)
        self.assertGreater(snapshot.pct_retroactive_gt4h, 0)
        # 12h delay is >4h but not >24h
        self.assertEqual(snapshot.pct_retroactive_gt24h, 0)

    def test_real_time_activity_not_flagged_as_retroactive(self):
        mission = self._make_mission(DAY_START + timedelta(hours=9))
        # Only 5 minutes delay → not retroactive
        self._make_activity(
            mission,
            start_time=DAY_START + timedelta(hours=8, minutes=55),
            reception_time=DAY_START + timedelta(hours=9),
        )

        _compute_and_store_snapshots(SNAPSHOT_DATE)

        snapshot = SoftwareComplianceSnapshot.query.filter_by(
            client_id=self.oauth_client.id, snapshot_date=SNAPSHOT_DATE
        ).one()
        self.assertEqual(snapshot.pct_retroactive_gt4h, 0)
        self.assertEqual(snapshot.pct_retroactive_gt24h, 0)

    def test_mission_without_vehicle_flagged(self):
        mission = self._make_mission(DAY_START + timedelta(hours=9))
        self.assertIsNone(mission.vehicle_id)
        self._make_activity(
            mission,
            start_time=DAY_START + timedelta(hours=8, minutes=55),
            reception_time=DAY_START + timedelta(hours=9),
        )

        _compute_and_store_snapshots(SNAPSHOT_DATE)

        snapshot = SoftwareComplianceSnapshot.query.filter_by(
            client_id=self.oauth_client.id, snapshot_date=SNAPSHOT_DATE
        ).one()
        self.assertEqual(snapshot.pct_missing_vehicle, 100.0)

    def test_no_alert_before_7_consecutive_active_days(self):
        self._make_snapshots(6, pct_retroactive_gt4h=99.0)
        self.assertEqual(
            _get_violations(self.oauth_client.id, date.today()), []
        )

    def test_alert_triggered_on_day_7(self):
        self._make_snapshots(7, pct_retroactive_gt4h=99.0)
        violations = _get_violations(self.oauth_client.id, date.today())
        self.assertTrue(any("Rétro-saisie" in v for v in violations))

    def test_no_alert_on_day_8_between_reminders(self):
        # Day 8 of streak: 8 % 7 != 0 → no alert until day 14
        self._make_snapshots(8, pct_retroactive_gt4h=99.0)
        self.assertEqual(
            _get_violations(self.oauth_client.id, date.today()), []
        )

    def test_weekly_reminder_sent_on_day_14(self):
        self._make_snapshots(14, pct_retroactive_gt4h=99.0)
        violations = _get_violations(self.oauth_client.id, date.today())
        self.assertTrue(any("semaine 2" in v for v in violations))
