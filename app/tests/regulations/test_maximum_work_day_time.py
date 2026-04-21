from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from app import db
from app.domain.log_activities import log_activity
from app.domain.regulations_per_day import NATINF_32083, NATINF_11292
from app.domain.validation import validate_mission
from app.helpers.regulations_utils import HOUR
from app.helpers.submitter_type import SubmitterType
from app.models import (
    Mission,
    RegulatoryAlert,
    User,
    RegulationCheck,
)
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.seed import UserFactory, EmploymentFactory, AuthenticatedUserContext
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


def _get_alert(days_ago, submitter_type=SubmitterType.EMPLOYEE):
    """Get regulatory alert for a date relative to today (days ago)"""
    day_start = get_date(days_ago)
    return _get_alert_for_date(day_start, submitter_type)


class TestMaximumWorkDayTime(RegulationsTest):
    def test_max_work_day_time_by_employee_success(self):
        how_many_days_ago = 2
        self._log_and_validate_mission(
            mission_name="Transfer & night work tarification but not legislation",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=3),
                    get_time(how_many_days_ago=how_many_days_ago, hour=5),
                    ActivityType.TRANSFER,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=5),
                    get_time(how_many_days_ago=how_many_days_ago, hour=16),
                ],
            ],
        )
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_max_work_day_time_by_employee_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="3h work (night) + 8h drive",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=4),
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=8),
                    get_time(how_many_days_ago=how_many_days_ago, hour=16),
                ],
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], True)
        self.assertIsNotNone(extra_info["max_work_range_in_hours"])
        self.assertEqual(extra_info["work_range_in_seconds"], 11 * HOUR)
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_start"]),
            get_time(how_many_days_ago, hour=4),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_end"]),
            get_time(how_many_days_ago, hour=16),
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_32083)

    def test_max_work_day_time_by_employee_no_night_work_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="5h work + 8h drive",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    get_time(how_many_days_ago=how_many_days_ago, hour=12),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=13),
                    get_time(how_many_days_ago=how_many_days_ago, hour=21),
                ],
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], False)
        self.assertIsNotNone(extra_info["max_work_range_in_hours"])
        self.assertEqual(extra_info["work_range_in_seconds"], 13 * HOUR)
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_start"]),
            get_time(how_many_days_ago, hour=7),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_end"]),
            get_time(how_many_days_ago, hour=21),
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_11292)

    def test_long_break_resets_counters(self):
        """Test long break (>=10h) resets work counters"""
        how_many_days_ago = 2

        # Mission 1: Activity spanning midnight (Aug 5 21:39 → Aug 6 00:44)
        # Represents 3h05 of work crossing the day boundary
        self._log_and_validate_mission(
            mission_name="Mission spanning midnight",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=21, minute=39
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=0,
                        minute=44,
                    ),
                    ActivityType.DRIVE,
                ],
            ],
        )

        # Mission 2: Activities on Aug 6 after 14h16 break
        # Increased work time to exceed 10h total and test the long break reset
        self._log_and_validate_mission(
            mission_name="Mission after 14h16 break",
            submitter=self.employee,
            work_periods=[
                # 15:00 → 17:30 (2h30)
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=15,
                        minute=0,
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=17,
                        minute=30,
                    ),
                    ActivityType.DRIVE,
                ],
                # 18:00 → 21:00 (3h00)
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=18,
                        minute=0,
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=21,
                        minute=0,
                    ),
                    ActivityType.DRIVE,
                ],
                # 21:30 → 23:30 (2h00)
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=21,
                        minute=30,
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=23,
                        minute=30,
                    ),
                    ActivityType.DRIVE,
                ],
            ],
        )

        def _get_alert(days_ago):
            day_start = get_time(days_ago, hour=0).date()
            return _get_alert_for_date(day_start)

        # Day 1 (Aug 5): No alert expected (3h05 < 10h limit)
        regulatory_alert_day1 = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(
            regulatory_alert_day1,
            "Aug 5: 3h05 work time < 10h limit → no alert expected",
        )

        # Day 2 (Aug 6): No alert expected after fix
        # Long break (14h16) should reset counters, so only 7h30 counted instead of cumulative time > 10h
        regulatory_alert_day2 = _get_alert(days_ago=how_many_days_ago - 1)

        self.assertIsNone(
            regulatory_alert_day2,
            "Aug 6: Long break (14h16) should reset work counters → no false alert",
        )

    def test_short_break_still_triggers_alert(self):
        """Control test: alerts still work when break < 10h threshold"""
        how_many_days_ago = 3

        self._log_and_validate_mission(
            mission_name="Consecutive missions with short break",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=8),
                    get_time(how_many_days_ago=how_many_days_ago, hour=14),
                    ActivityType.DRIVE,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=16),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=22, minute=10
                    ),
                    ActivityType.DRIVE,
                ],
            ],
        )

        # Alert MUST be triggered here (2h break < 10h threshold)
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(
            regulatory_alert,
            "With short break (<10h), alert should be triggered for excessive work time",
        )

        extra_info = regulatory_alert.extra
        # Verify that calculated time includes both missions
        total_work_seconds = extra_info["work_range_in_seconds"]
        total_work_hours = total_work_seconds / HOUR
        self.assertGreater(
            total_work_hours,
            10,
            "Total work time must exceed 10h to trigger the alert",
        )

    def test_max_work_day_time_depending_on_business(self):
        how_many_days_ago = 5

        ## By default, employee is TRM
        self._log_and_validate_mission(
            mission_name="11h - ok",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    get_time(how_many_days_ago=how_many_days_ago, hour=12),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=13),
                    get_time(how_many_days_ago=how_many_days_ago, hour=19),
                ],
            ],
        )

        # 11h  is fine, no alert
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

        self.convert_employee_to_trv()

        how_many_days_ago = 2

        ## now employee is TRV
        self._log_and_validate_mission(
            mission_name="11h - ko",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    get_time(how_many_days_ago=how_many_days_ago, hour=12),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=13),
                    get_time(how_many_days_ago=how_many_days_ago, hour=19),
                ],
            ],
        )

        # 11h  is above limit, alert
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)

    def test_max_work_day_time_by_admin_failure(self):
        how_many_days_ago = 2

        mission = self._log_and_validate_mission(
            mission_name="3h work (night) + 10h drive",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=4),
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    ActivityType.WORK,
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=7),
                    get_time(how_many_days_ago=how_many_days_ago, hour=17),
                ],
            ],
        )
        with AuthenticatedUserContext(user=self.admin):
            validate_mission(
                submitter=self.admin, mission=mission, for_user=self.employee
            )

        regulatory_alert = _get_alert(
            days_ago=how_many_days_ago, submitter_type=SubmitterType.ADMIN
        )
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], True)
        self.assertIsNotNone(extra_info["max_work_range_in_hours"])
        self.assertEqual(extra_info["work_range_in_seconds"], 13 * HOUR)
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_start"]),
            get_time(how_many_days_ago, hour=4),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_end"]),
            get_time(how_many_days_ago, hour=17),
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_32083)

    def test_max_work_day_time_in_guyana_success(self):
        company = self.company
        admin = self.admin
        how_many_days_ago = 2

        GY_TZ_NAME = "America/Cayenne"
        GY_TIMEZONE = ZoneInfo(GY_TZ_NAME)

        employee = UserFactory.create(
            email="employee-guyana@email.com",
            password="password",
            timezone_name=GY_TZ_NAME,
        )
        EmploymentFactory.create(
            company=company,
            submitter=admin,
            user=employee,
            has_admin_rights=False,
        )

        mission = Mission(
            name="11h drive in Guyana with night work",
            company=company,
            reception_time=datetime.now(),
            submitter=employee,
        )
        db.session.add(mission)
        db.session.commit()

        with AuthenticatedUserContext(user=employee):
            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(
                    how_many_days_ago, hour=17, tz=GY_TIMEZONE
                ),
                start_time=get_time(how_many_days_ago, hour=6, tz=GY_TIMEZONE),
                end_time=get_time(how_many_days_ago, hour=17, tz=GY_TIMEZONE),
            )

            # Guyana UTC-4 = France UTC+2
            # Guyana: 6h -> 17h (day)
            # France: 12h -> 23h (night)

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        regulatory_alert = _get_alert(
            days_ago=how_many_days_ago, submitter_type=SubmitterType.ADMIN
        )
        self.assertIsNone(regulatory_alert)

    def test_night_hours_start(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="Travail de nuit",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=13, minute=55
                    ),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=0),
                    ActivityType.WORK,
                ],
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], True)

    def test_no_night_hours_start(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="Pas de travail de nuit",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=9, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=23, minute=55
                    ),
                    ActivityType.WORK,
                ],
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], False)

    def test_night_hours_end(self):
        how_many_days_ago = 2

        # Let's check night hours ends at 5am
        self._log_and_validate_mission(
            mission_name="Travail de nuit",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=4, minute=50
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=14, minute=55
                    ),
                    ActivityType.WORK,
                ],
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], True)

    def test_no_night_hours_end(self):
        how_many_days_ago = 2

        # Let's check night hours ends at 5am
        self._log_and_validate_mission(
            mission_name="Pas de travail de nuit",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=5, minute=5
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=18, minute=0
                    ),
                    ActivityType.WORK,
                ],
            ],
        )

        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["night_work"], False)

    ## T3P (Taxi, VTC, LOTI)
    ## 9h if amplitude > 12h
    ## 10h if amplitude <= 12h
    def test_ok_t3p_low_amplitude(self):
        how_many_days_ago = 2
        self.convert_employee_to_vtc()

        self._log_and_validate_mission(
            mission_name="11h amplitude - 9h30 travail",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=0
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=12, minute=30
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=17, minute=0
                    ),
                ],
            ],
        )
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_ko_t3p_low_amplitude(self):
        how_many_days_ago = 2
        self.convert_employee_to_vtc()

        self._log_and_validate_mission(
            mission_name="11h amplitude - 10h30 travail",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=0
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=30
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=17, minute=0
                    ),
                ],
            ],
        )
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)

    def test_ok_t3p_high_amplitude(self):
        how_many_days_ago = 2
        self.convert_employee_to_vtc()

        self._log_and_validate_mission(
            mission_name="13h amplitude - 8h30 travail",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=0
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=15, minute=30
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=19, minute=0
                    ),
                ],
            ],
        )
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_ko_t3p_high_amplitude(self):
        how_many_days_ago = 2
        self.convert_employee_to_vtc()

        self._log_and_validate_mission(
            mission_name="13h amplitude - 9h30 travail",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=0
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=14, minute=30
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=19, minute=0
                    ),
                ],
            ],
        )
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)

    ## TRV Frequent
    ## 9h if amplitude > 13h
    ## 10h if amplitude <= 13h
    def test_ok_trv_frequent_low_amplitude(self):
        how_many_days_ago = 2
        self.convert_employee_to_trv()

        self._log_and_validate_mission(
            mission_name="12h amplitude - 9h30 travail",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=0
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=13, minute=30
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=18, minute=0
                    ),
                ],
            ],
        )
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_ko_trv_frequent_low_amplitude(self):
        how_many_days_ago = 2
        self.convert_employee_to_trv()

        self._log_and_validate_mission(
            mission_name="12h amplitude - 10h30 travail",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=0
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=12, minute=30
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=18, minute=0
                    ),
                ],
            ],
        )
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)

    def test_ok_trv_frequent_high_amplitude(self):
        how_many_days_ago = 2
        self.convert_employee_to_trv()

        self._log_and_validate_mission(
            mission_name="13h30 amplitude - 8h30 travail",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=0
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=16, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=19, minute=30
                    ),
                ],
            ],
        )
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNone(regulatory_alert)

    def test_ko_trv_frequent_high_amplitude(self):
        how_many_days_ago = 2
        self.convert_employee_to_trv()

        self._log_and_validate_mission(
            mission_name="13h30 amplitude - 9h30 travail",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=6, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=0
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=15, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=19, minute=30
                    ),
                ],
            ],
        )
        regulatory_alert = _get_alert(days_ago=how_many_days_ago)
        self.assertIsNotNone(regulatory_alert)

    def test_night_work_on_two_days(self):
        how_many_days_ago = 2
        self._log_and_validate_mission(
            mission_name="",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=20),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=7,
                        minute=30,
                    ),
                ],
            ],
        )
        alert = _get_alert(days_ago=2)
        self.assertIsNotNone(alert)

    def test_production_case_august_2025(self):
        """Test work time calculation with production data from August 5-7, 2025"""

        # Specific helpers for more precise datetime handling
        def get_time_for_date(target_date, hour, minute=0):
            """Generate datetime for exact date with specific hour/minute"""
            return datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                minute,
            )

        def _get_alert_for_date(target_date):
            """Get any regulatory alert for the specified date"""
            return RegulatoryAlert.query.filter(
                RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
                RegulatoryAlert.regulation_check.has(
                    RegulationCheck.type
                    == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
                ),
                RegulatoryAlert.day == target_date,
                RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
            ).one_or_none()

        # Production dates - using exact dates from the real case
        aug_5_2025 = datetime(2025, 8, 5).date()
        aug_6_2025 = datetime(2025, 8, 6).date()
        aug_7_2025 = datetime(2025, 8, 7).date()

        with freeze_time(aug_5_2025):
            # Mission 1: August 5, 2025 (mission_id: 6159946)
            mission1 = self._log_and_validate_mission(
                mission_name="Mission 6159946 - Aug 5",
                submitter=self.employee,
                work_periods=[
                    # Activity 1: 15:02-16:50 UTC = 17:02-18:50 Paris (1h48)
                    [
                        get_time_for_date(aug_5_2025, 15, 2),
                        get_time_for_date(aug_5_2025, 16, 50),
                    ],
                    # Activity 2: 17:06-19:09 UTC = 19:06-21:09 Paris (2h03)
                    [
                        get_time_for_date(aug_5_2025, 17, 6),
                        get_time_for_date(aug_5_2025, 19, 9),
                    ],
                    # Activity 3: 19:39-22:44 UTC = 21:39-00:44+1 Paris (3h05)
                    [
                        get_time_for_date(aug_5_2025, 19, 39),
                        get_time_for_date(aug_5_2025, 22, 44),
                    ],
                ],
            )

        with freeze_time(aug_6_2025):
            # Break: 14h16 (22:44 Aug 5 → 13:00 Aug 6 UTC)

            # Mission 2: August 6, 2025 (mission_id: 6170713)
            mission2 = self._log_and_validate_mission(
                mission_name="Mission 6170713 - Aug 6",
                submitter=self.employee,
                work_periods=[
                    # Activity 1: 13:00-14:44 UTC = 15:00-16:44 Paris (1h44)
                    [
                        get_time_for_date(aug_6_2025, 13, 0),
                        get_time_for_date(aug_6_2025, 14, 44),
                    ],
                    # Activity 2: 15:00-17:00 UTC = 17:00-19:00 Paris (2h00)
                    [
                        get_time_for_date(aug_6_2025, 15, 0),
                        get_time_for_date(aug_6_2025, 17, 0),
                    ],
                    # Activity 3: 17:30-20:28 UTC = 19:30-22:28 Paris (2h58)
                    [
                        get_time_for_date(aug_6_2025, 17, 30),
                        get_time_for_date(aug_6_2025, 20, 28),
                    ],
                ],
            )

        with freeze_time(aug_7_2025):
            # Mission 3: August 7, 2025 (mission_id: 6181364)
            mission3 = self._log_and_validate_mission(
                mission_name="Mission 6181364 - Aug 7",
                submitter=self.employee,
                work_periods=[
                    # Activity 1: 15:01-16:55 UTC = 17:01-18:55 Paris (1h54)
                    [
                        get_time_for_date(aug_7_2025, 15, 1),
                        get_time_for_date(aug_7_2025, 16, 55),
                    ],
                    # Activity 2: 17:11-19:02 UTC = 19:11-21:02 Paris (1h51)
                    [
                        get_time_for_date(aug_7_2025, 17, 11),
                        get_time_for_date(aug_7_2025, 19, 2),
                    ],
                    # Activity 3: 19:33-22:45 UTC = 21:33-00:45+1 Paris (3h12)
                    [
                        get_time_for_date(aug_7_2025, 19, 33),
                        get_time_for_date(aug_7_2025, 22, 45),
                    ],
                ],
            )

            # Verify no false alerts are generated
            alert_august_5 = _get_alert_for_date(aug_5_2025)
            alert_august_6 = _get_alert_for_date(aug_6_2025)
            alert_august_7 = _get_alert_for_date(aug_7_2025)

            # Mission 1 work time: 1h48 + 2h03 + 3h05 ≈ 6h56 (under 10h limit)
            self.assertIsNone(
                alert_august_5,
                "No alert for Aug 5: ≈6h56 work is below 10h limit",
            )

            # Mission 2 work time: 1h44 + 2h00 + 2h58 ≈ 6h42 (under 10h limit)
            # Should not cumulate with Mission 1 due to 14h16 break triggering counter reset
            self.assertIsNone(
                alert_august_6,
                "No alert for Aug 6: ≈6h42 work is below 10h limit after break reset",
            )

            # Mission 3 work time: 1h54 + 1h51 + 3h12 ≈ 6h57 (under 10h limit)
            self.assertIsNone(
                alert_august_7,
                "No alert for Aug 7: ≈6h57 work is below 10h limit",
            )
