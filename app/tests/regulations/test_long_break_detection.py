"""
Tests for long break detection and work time counter reset.

These tests verify that work time counters are properly reset after
a long break (> 10 hours) to prevent incorrect regulatory alerts.
"""

from datetime import datetime
from app.domain.regulations_per_day import NATINF_32083
from app.helpers.submitter_type import SubmitterType
from app.models import RegulatoryAlert, User, RegulationCheck
from app.models.regulation_check import RegulationCheckType
from app.seed.helpers import get_time, get_date
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


def _get_alert_for_date(target_date, submitter_type=SubmitterType.EMPLOYEE):
    """Get regulatory alert for a specific date"""
    return RegulatoryAlert.query.filter(
        RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
        RegulatoryAlert.regulation_check.has(
            RegulationCheck.type == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
        ),
        RegulatoryAlert.day == target_date,
        RegulatoryAlert.submitter_type == submitter_type,
    ).one_or_none()


class TestLongBreakDetection(RegulationsTest):
    DAYS_BEFORE_TODAY_FOR_TEST = 2

    def test_long_break_should_reset_work_time_counters(self):
        """
        Scenario:
        - Driver works night shift (~5h night work)
        - Takes a LONG BREAK of 16h53 (> 10h minimum)
        - Resumes evening work (~9h night work)

        Expected:
        - Work time counters reset after long break
        - NO alert (each period < 10h)

        Bug (if present):
        - Alert generated for continuous night work exceeding limit
        """

        how_many_days_ago = self.DAYS_BEFORE_TODAY_FOR_TEST

        # Mission 1: Night shift
        # Activity from 22:46 to 03:32 (~5h night work)
        self._log_and_validate_mission(
            mission_name="Mission nuit",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago + 1,
                        hour=22,
                        minute=46,
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=3, minute=32
                    ),
                ],
            ],
        )

        # PAUSE LONGUE : 03:32 → 20:25 (environ 17h - bien > 10h)

        # Mission 2 : Soir jusqu'au lendemain matin
        # Activité de 20:25 à 05:45 le lendemain (environ 9h de travail de nuit)
        self._log_and_validate_mission(
            mission_name="Mission soir",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=20, minute=25
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=5,
                        minute=45,
                    ),
                ],
            ],
        )

        # Check alerts for the target day
        day_start = get_date(how_many_days_ago)
        alert = _get_alert_for_date(day_start)

        if alert:
            print(f"\n❌ Alert found (BUG):")
            print(f"  - Day: {alert.day}")
            print(f"  - Regulation: {alert.regulation_check.regulation_rule}")
            print(f"  - Extra: {alert.extra}")
            print(f"  - Sanction: {alert.extra.get('sanction_code')}")
            print(
                f"  - Work duration: {alert.extra.get('work_range_in_seconds')}s = {alert.extra.get('work_range_in_seconds') / 3600:.1f}h"
            )

        self.assertIsNone(
            alert,
            f"No alert should be generated because the 17h break resets counters. "
            f"Alert found: {alert.extra if alert else None}",
        )

    def test_exact_user_scenario_with_multiple_missions(self):
        """
        Reproduces exact user scenario with 3 separate missions.

        Mission 1 (06/01): 23:46 → 01:57
        Mission 2 (06-07/01): 01:57 → 04:32
        Mission 3 (07-08/01): 05:00 → 06:41, PAUSE 14h44, then 21:25 → 06:45

        The 14h44 pause should reset work time counters.
        """
        how_many_days_ago = self.DAYS_BEFORE_TODAY_FOR_TEST

        # Mission 1: 06/01 23:46 → 07/01 01:57
        self._log_and_validate_mission(
            mission_name="Mission 1",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago + 1,
                        hour=23,
                        minute=46,
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=1, minute=57
                    ),
                ],
            ],
        )

        # Mission 2: 07/01 01:57 → 04:32
        self._log_and_validate_mission(
            mission_name="Mission 2",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=1, minute=57
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=3, minute=3
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=3, minute=3
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=4, minute=32
                    ),
                ],
            ],
        )

        # Mission 3: Matin + Soir avec LONGUE PAUSE au milieu
        # 07/01 05:00 → 06:41
        # PAUSE 14h44 (06:41 → 21:25)
        # 07/01 21:25 → 08/01 06:45
        self._log_and_validate_mission(
            mission_name="Mission 3",
            submitter=self.employee,
            work_periods=[
                # Matin
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=5, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=41
                    ),
                ],
                # Evening (after 14h44 break)
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=21, minute=25
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=21, minute=41
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=21, minute=41
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=23, minute=42
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=23, minute=42
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=1,
                        minute=58,
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=2,
                        minute=44,
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=2,
                        minute=59,
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=2,
                        minute=59,
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=4,
                        minute=55,
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=5,
                        minute=9,
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=6,
                        minute=45,
                    ),
                ],
            ],
        )

        day_start = get_date(how_many_days_ago)
        alert = _get_alert_for_date(day_start)

        if alert:
            print(f"\n❌ BUG REPRODUCED!")
            print(f"  - Day: {alert.day}")
            print(
                f"  - work_range_start: {alert.extra.get('work_range_start')}"
            )
            print(f"  - work_range_end: {alert.extra.get('work_range_end')}")
            print(
                f"  - work_range_in_seconds: {alert.extra.get('work_range_in_seconds')}s = {alert.extra.get('work_range_in_seconds') / 3600:.2f}h"
            )
            print(f"  - Sanction: {alert.extra.get('sanction_code')}")
            print(f"\n  ⚠️ The 06:41 → 21:25 break (14h44) was NOT detected!")
        else:
            print(f"\n✅ No alert - Bug NOT reproduced with this scenario")

        self.assertIsNone(
            alert,
            f"Bug reproduced! The 14h44 break did not reset counters. "
            f"Alert: {alert.extra if alert else None}",
        )

    def test_without_long_break_should_generate_alert(self):
        """
        Control scenario: Without a long break, alert SHOULD be generated.
        """

        how_many_days_ago = self.DAYS_BEFORE_TODAY_FOR_TEST

        # Continuous night work with short break (< 10h)
        # First period: 6h night work
        self._log_and_validate_mission(
            mission_name="Long mission part 1",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago + 1,
                        hour=22,
                        minute=46,
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=4, minute=46
                    ),
                ],
            ],
        )

        # Short 2h break (< 10h minimum)

        # Second period: Additional 6h = 12h total
        self._log_and_validate_mission(
            mission_name="Long mission part 2",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=46
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=12, minute=46
                    ),
                ],
            ],
        )

        day_start = get_date(how_many_days_ago)
        alert = _get_alert_for_date(day_start)

        self.assertIsNotNone(
            alert, "Alert should be generated for exceeding night work time"
        )

        self.assertEqual(
            alert.extra.get("sanction_code"),
            NATINF_32083,
            "Alert should be NATINF 32083 (night work time exceeded)",
        )
