"""
Non-regression test for the bug where regulatory alerts disappear
when modifying an activity in a mission following a continuous work
period spanning multiple missions.

Bug: When a regulatory alert concerns a work period spanning multiple
missions, modifying an activity in a later mission can incorrectly
cause the alert to disappear.

Real scenario reproducing the bug:
- Mission 1 (05-06/01): night work
- Mission 2 (06-07/01): continuous night work (no 11h break)
- Mission 3 (07-08/01): continuous night work (generates NATINF 32083 alert)
- Mission 4 (08/01 21:50-23:35): new activity added
  → Alert from mission 3 incorrectly disappears
"""

from datetime import datetime

from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.submitter_type import SubmitterType
from app.models import Mission, RegulatoryAlert, User, RegulationComputation
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.seed.helpers import AuthenticatedUserContext, get_datetime_tz
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestMultiMissionAlertBug(RegulationsTest):
    """
    Tests to reproduce and verify the fix for regulatory alert
    disappearance across multiple missions.
    """

    def test_alert_should_not_disappear_when_modifying_later_activity(self):
        """
        Tests that the NATINF 32083 alert (night work time exceeded)
        does NOT disappear when modifying an activity in a later mission.

        Steps:
        1. Create 3 consecutive missions with continuous night work (>10h)
        2. Verify that a NATINF 32083 alert is generated
        3. Add a 4th mission after a >11h break
        4. Verify that the alert from step 2 is STILL present
        """

        # ==== STEP 1: Create missions with continuous night work ====

        # Mission 1 : 05/01 21:26 → 06/01 02:43 (5h17 de nuit)
        mission1 = self._log_and_validate_mission(
            mission_name="Mission 1 - Nuit du 05 au 06",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2026, 1, 5, 21, 26),
                    get_datetime_tz(2026, 1, 5, 21, 33),
                    ActivityType.WORK,
                ],
                [
                    get_datetime_tz(2026, 1, 5, 21, 33),
                    get_datetime_tz(2026, 1, 6, 1, 59),
                    ActivityType.DRIVE,
                ],
                [
                    get_datetime_tz(2026, 1, 6, 1, 59),  # Pause < 11h
                    get_datetime_tz(2026, 1, 6, 2, 43),
                    ActivityType.WORK,
                ],
            ],
        )

        # Mission 2 : 06/01 02:55 → 06/01 23:46 (pause de 12min seulement)
        mission2 = self._log_and_validate_mission(
            mission_name="Mission 2 - Journée du 06",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2026, 1, 6, 2, 55),
                    get_datetime_tz(2026, 1, 6, 6, 18),
                    ActivityType.DRIVE,
                ],
                [
                    get_datetime_tz(
                        2026, 1, 6, 6, 18
                    ),  # Pause dans la journée
                    get_datetime_tz(2026, 1, 6, 21, 23),
                    ActivityType.WORK,
                ],
                [
                    get_datetime_tz(2026, 1, 6, 21, 23),
                    get_datetime_tz(2026, 1, 6, 23, 46),
                    ActivityType.DRIVE,
                ],
            ],
        )

        # Mission 3 : 06/01 23:46 → 07/01 06:41 (nuit continue)
        mission3 = self._log_and_validate_mission(
            mission_name="Mission 3 - Nuit du 06 au 07",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2026, 1, 6, 23, 46),
                    get_datetime_tz(2026, 1, 7, 1, 57),
                    ActivityType.DRIVE,
                ],
                [
                    get_datetime_tz(2026, 1, 7, 1, 57),  # Pause < 11h
                    get_datetime_tz(2026, 1, 7, 3, 3),
                    ActivityType.WORK,
                ],
                [
                    get_datetime_tz(2026, 1, 7, 3, 3),
                    get_datetime_tz(2026, 1, 7, 6, 41),
                    ActivityType.DRIVE,
                ],
            ],
        )

        db.session.commit()

        # ==== STEP 2: Verify that a NATINF 32083 alert is generated ====

        # Alert should be generated for night work time exceeded
        # (continuous night work period > 10h without 11h break)
        alerts_before = RegulatoryAlert.query.filter(
            RegulatoryAlert.user == self.employee,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()

        # Filtrer les alertes MAXIMUM_WORK_DAY_TIME (qui inclut NATINF 32083)
        night_work_alerts_before = [
            alert
            for alert in alerts_before
            if alert.regulation_check.type
            == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            and alert.extra
            and alert.extra.get("night_work") is True
            and alert.extra.get("sanction_code") == "NATINF 32083"
        ]

        # Display alerts for debugging
        print("\n=== Alerts BEFORE adding mission 4 ===")
        for alert in night_work_alerts_before:
            print(f"Day: {alert.day}, Extra: {alert.extra}")

        self.assertGreater(
            len(night_work_alerts_before),
            0,
            "Should have at least one NATINF 32083 alert for night work time exceeded",
        )

        # Save alert IDs and details for comparison
        alert_ids_before = {alert.id for alert in night_work_alerts_before}
        alert_days_before = {alert.day for alert in night_work_alerts_before}

        # ==== STEP 3: Add a 4th mission AFTER a >11h break ====

        # Mission 4: 08/01 21:50 → 08/01 23:35 (after ~15h break since 06:41)
        mission4 = self._log_and_validate_mission(
            mission_name="Mission 4 - Evening of 08th",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2026, 1, 8, 21, 50),
                    get_datetime_tz(2026, 1, 8, 23, 35),
                    ActivityType.DRIVE,
                ],
            ],
        )

        db.session.commit()

        # ==== STEP 4: Verify that the alert is STILL present ====

        alerts_after = RegulatoryAlert.query.filter(
            RegulatoryAlert.user == self.employee,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()

        night_work_alerts_after = [
            alert
            for alert in alerts_after
            if alert.regulation_check.type
            == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            and alert.extra
            and alert.extra.get("night_work") is True
            and alert.extra.get("sanction_code") == "NATINF 32083"
        ]

        print("\n=== Alerts AFTER adding mission 4 ===")
        for alert in night_work_alerts_after:
            print(f"Day: {alert.day}, Extra: {alert.extra}")

        alert_ids_after = {alert.id for alert in night_work_alerts_after}
        alert_days_after = {alert.day for alert in night_work_alerts_after}

        # Critical assertions
        self.assertEqual(
            len(night_work_alerts_after),
            len(night_work_alerts_before),
            f"Number of NATINF 32083 alerts changed! "
            f"Before: {len(night_work_alerts_before)}, After: {len(night_work_alerts_after)}. "
            f"Alert likely disappeared when adding mission 4.",
        )

        self.assertEqual(
            alert_days_after,
            alert_days_before,
            f"Alert days changed! "
            f"Before: {alert_days_before}, After: {alert_days_after}",
        )

        # Verify that the original alerts are still there
        # (may have new IDs if recreated, but must exist)
        for day in alert_days_before:
            alerts_for_day = [
                a for a in night_work_alerts_after if a.day == day
            ]
            self.assertGreater(
                len(alerts_for_day), 0, f"Alert for day {day} has disappeared!"
            )

    def test_alert_should_disappear_when_long_break_follows(self):
        """
        Tests that the NATINF 32083 alert (night work time exceeded)
        CORRECTLY DISAPPEARS when a long break (>10h) follows.

        This test verifies that the Bug 2 fix (long break detection) works
        and that invalid alerts are properly removed during recalculation.
        """

        # Create a continuous night work period
        mission1 = self._log_and_validate_mission(
            mission_name="Long night shift part 1",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2026, 1, 6, 22, 0),
                    get_datetime_tz(2026, 1, 7, 3, 0),
                    ActivityType.DRIVE,
                ],
            ],
        )

        mission2 = self._log_and_validate_mission(
            mission_name="Long night shift part 2",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2026, 1, 7, 3, 0),  # Pas de pause
                    get_datetime_tz(2026, 1, 7, 9, 0),
                    ActivityType.DRIVE,
                ],
            ],
        )

        db.session.commit()

        # Get the generated alert (11h continuous night work)
        alert_before = (
            RegulatoryAlert.query.filter(
                RegulatoryAlert.user == self.employee,
                RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
                RegulatoryAlert.regulation_check.has(
                    type=RegulationCheckType.MAXIMUM_WORK_DAY_TIME
                ),
            )
            .filter(RegulatoryAlert.extra["night_work"].astext == "true")
            .first()
        )

        self.assertIsNotNone(
            alert_before,
            "Should have a night work alert before the long break",
        )

        # Save details for documentation
        work_range_start_before = alert_before.extra.get("work_range_start")
        work_range_end_before = alert_before.extra.get("work_range_end")
        work_duration_before = alert_before.extra.get("work_range_in_seconds")

        print(f"\n=== Alert BEFORE long break ===")
        print(f"Period: {work_range_start_before} → {work_range_end_before}")
        print(
            f"Duration: {work_duration_before}s = {work_duration_before/3600:.2f}h"
        )

        # Add a mission AFTER a long break >10h (12h after the end of mission2)
        mission3 = self._log_and_validate_mission(
            mission_name="Next day mission after long break",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2026, 1, 7, 21, 0),  # 12h later (9h → 21h)
                    get_datetime_tz(2026, 1, 7, 23, 0),
                    ActivityType.DRIVE,
                ],
            ],
        )

        db.session.commit()

        # Get alerts after the long break
        alerts_after = (
            RegulatoryAlert.query.filter(
                RegulatoryAlert.user == self.employee,
                RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
                RegulatoryAlert.regulation_check.has(
                    type=RegulationCheckType.MAXIMUM_WORK_DAY_TIME
                ),
            )
            .filter(RegulatoryAlert.extra["night_work"].astext == "true")
            .all()
        )

        print(f"\n=== Alerts AFTER long break ===")
        print(f"Number of alerts: {len(alerts_after)}")
        for alert in alerts_after:
            print(
                f"Day: {alert.day}, Period: {alert.extra.get('work_range_start')} → {alert.extra.get('work_range_end')}"
            )

        # The previous alert should have disappeared because the long break resets the counters
        # Mission 3 alone (2h) does NOT generate an alert
        self.assertEqual(
            len(alerts_after),
            0,
            "Alert should have disappeared after a 12h long break. "
            "If it persists, the long break detection bug is not fixed.",
        )

    def test_computation_is_marked_for_all_affected_days(self):
        """
        Tests that RegulationComputation is marked for ALL days
        affected by a multi-mission alert, not just the day of the validated mission.
        """

        # Create missions that generate an alert spanning multiple days
        self._log_and_validate_mission(
            mission_name="Day 1",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2026, 1, 6, 22, 0),
                    get_datetime_tz(2026, 1, 7, 2, 0),
                    ActivityType.DRIVE,
                ],
            ],
        )

        self._log_and_validate_mission(
            mission_name="Day 2",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2026, 1, 7, 2, 0),
                    get_datetime_tz(2026, 1, 7, 10, 0),
                    ActivityType.DRIVE,
                ],
            ],
        )

        db.session.commit()

        # Verify that computations exist for the affected days
        computation_day1 = RegulationComputation.query.filter(
            RegulationComputation.user == self.employee,
            RegulationComputation.day
            == get_datetime_tz(2026, 1, 6, 0, 0).date(),
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).first()

        computation_day2 = RegulationComputation.query.filter(
            RegulationComputation.user == self.employee,
            RegulationComputation.day
            == get_datetime_tz(2026, 1, 7, 0, 0).date(),
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).first()

        self.assertIsNotNone(
            computation_day1, "Computation should be marked for day 1"
        )
        self.assertIsNotNone(
            computation_day2, "Computation should be marked for day 2"
        )
