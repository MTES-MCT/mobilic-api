from datetime import datetime

from app import db
from app.domain.log_activities import log_activity
from app.domain.regulations_per_day import SANCTION_CODE
from app.domain.validation import validate_mission
from app.helpers.regulations_utils import MINUTE, HOUR
from app.helpers.time import FR_TIMEZONE
from app.models import Mission
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.seed.helpers import get_date, get_time, AuthenticatedUserContext
from app.tests.regulations import RegulationsTest


class TestWorkDayBreak(RegulationsTest):
    def test_min_work_day_break_by_employee_success(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="8h30 work with 30m break",
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=16),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=22, minute=14
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=22, minute=45
                    ),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=1),
                    ActivityType.WORK,
                ],
            ],
        )
        day_start = get_date(how_many_days_ago)
        regulatory_alert = self._get_regulatory_alert_employee(
            RegulationCheckType.MINIMUM_WORK_DAY_BREAK, day_start
        )

        self.assertIsNone(regulatory_alert)

    def test_min_work_day_break_by_employee_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="9h30 work with 30m break",
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=15),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=22, minute=15
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=22, minute=45
                    ),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=1),
                    ActivityType.WORK,
                ],
            ],
        )
        day_start = get_date(how_many_days_ago)
        regulatory_alert = self._get_regulatory_alert_employee(
            RegulationCheckType.MINIMUM_WORK_DAY_BREAK, day_start
        )

        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["min_break_time_in_minutes"], 45)
        self.assertEqual(
            extra_info["total_break_time_in_seconds"], 30 * MINUTE
        )
        self.assertEqual(
            extra_info["work_range_in_seconds"], 9 * HOUR + 30 * MINUTE
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_start"]),
            get_time(how_many_days_ago, hour=15, tz=FR_TIMEZONE),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_end"]),
            get_time(how_many_days_ago - 1, hour=1, tz=FR_TIMEZONE),
        )
        self.assertEqual(extra_info["sanction_code"], SANCTION_CODE)

    def test_min_work_day_break_by_employee_failure_single_day(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 2

        mission = Mission(
            name="9h30 work with 30m break",
            company=company,
            reception_time=datetime.now(),
            submitter=employee,
        )
        db.session.add(mission)

        with AuthenticatedUserContext(user=employee):
            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(
                    how_many_days_ago, hour=23, minute=15, tz=FR_TIMEZONE
                ),
                start_time=get_time(how_many_days_ago, hour=3, tz=FR_TIMEZONE),
                end_time=get_time(
                    how_many_days_ago, hour=10, minute=15, tz=FR_TIMEZONE
                ),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=False,
                reception_time=get_time(
                    how_many_days_ago, hour=22, tz=FR_TIMEZONE
                ),
                start_time=get_time(
                    how_many_days_ago, hour=10, minute=45, tz=FR_TIMEZONE
                ),
                end_time=get_time(how_many_days_ago, hour=13, tz=FR_TIMEZONE),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)
        regulatory_alert = self._get_regulatory_alert_employee(
            RegulationCheckType.MINIMUM_WORK_DAY_BREAK, day_start
        )

        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["min_break_time_in_minutes"], 45)
        self.assertEqual(
            extra_info["total_break_time_in_seconds"], 30 * MINUTE
        )
        self.assertEqual(
            extra_info["work_range_in_seconds"], 9 * HOUR + 30 * MINUTE
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_start"]),
            get_time(how_many_days_ago, hour=3, tz=FR_TIMEZONE),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_end"]),
            get_time(how_many_days_ago, hour=13, tz=FR_TIMEZONE),
        )
        self.assertEqual(extra_info["sanction_code"], SANCTION_CODE)

    def test_min_work_day_break_on_two_days(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="",
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=20),
                    get_time(how_many_days_ago=how_many_days_ago, hour=23),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=23),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=1,
                        minute=30,
                    ),
                    ActivityType.WORK,
                ],
            ],
        )
        day_start = get_date(how_many_days_ago)

        regulatory_alert = self._get_regulatory_alert_employee(
            RegulationCheckType.MINIMUM_WORK_DAY_BREAK, day_start
        )
        self.assertIsNone(regulatory_alert)

    def test_very_long_mission_has_correct_extra(self):
        how_many_days_ago = 4

        self._log_and_validate_mission(
            mission_name="",
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=6),
                    get_time(how_many_days_ago=how_many_days_ago - 2, hour=20),
                ],
            ],
        )
        regulatory_alerts = self._get_regulatory_alerts_employee(
            RegulationCheckType.MINIMUM_WORK_DAY_BREAK
        )
        self.assertEqual(3, len(regulatory_alerts))

        extras = [ra.extra for ra in regulatory_alerts]
        self.assertEqual(
            (18 + 24 + 20) * HOUR, extras[0].get("work_range_in_seconds")
        )
        self.assertEqual(
            (18 + 24 + 20) * HOUR, extras[1].get("work_range_in_seconds")
        )
        self.assertEqual(
            (18 + 24 + 20) * HOUR, extras[2].get("work_range_in_seconds")
        )

    def test_mission_over_two_days_has_correct_trigger(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="",
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=22),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=5),
                ],
            ],
        )
        regulatory_alert = self._get_regulatory_alert_employee(
            RegulationCheckType.MINIMUM_WORK_DAY_BREAK
        )
        extra = regulatory_alert.extra
        self.assertEqual(30, extra.get("min_break_time_in_minutes"))

    def test_long_mission_over_two_days_has_correct_trigger(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="",
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=19),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=5),
                ],
            ],
        )
        regulatory_alert = self._get_regulatory_alert_employee(
            RegulationCheckType.MINIMUM_WORK_DAY_BREAK
        )
        extra = regulatory_alert.extra
        self.assertEqual(45, extra.get("min_break_time_in_minutes"))

    def test_two_missions_over_two_days_has_correct_extra(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="",
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=21),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=23, minute=58
                    ),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=0),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=4),
                ],
            ],
        )
        regulatory_alert = self._get_regulatory_alert_employee(
            RegulationCheckType.MINIMUM_WORK_DAY_BREAK
        )
        extra = regulatory_alert.extra
        self.assertEqual(30, extra.get("min_break_time_in_minutes"))
        self.assertEqual(
            4 * HOUR + 2 * HOUR + 58 * MINUTE,
            extra.get("work_range_in_seconds"),
        )
