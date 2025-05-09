from datetime import datetime, date
from freezegun import freeze_time

from app import db
from app.domain.log_activities import log_activity
from app.domain.regulations_per_day import NATINF_35187
from app.domain.validation import validate_mission
from app.helpers.regulations_utils import MINUTE, HOUR
from app.helpers.submitter_type import SubmitterType
from app.helpers.time import FR_TIMEZONE
from app.models import RegulatoryAlert, RegulationCheck, User, Mission
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.seed.helpers import get_date, get_time, AuthenticatedUserContext
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestWorkDayBreak(RegulationsTest):
    def _get_alert(self, day_start):
        return RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.ENOUGH_BREAK
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()

    def test_min_work_day_break_by_employee_success(self):
        # freeze date out of clock change day to avoid errors when it happens
        with freeze_time(date(2025, 4, 5)):
            how_many_days_ago = 2

            self._log_and_validate_mission(
                mission_name="8h30 work with 30m break",
                submitter=self.employee,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=16),
                        get_time(
                            how_many_days_ago=how_many_days_ago,
                            hour=22,
                            minute=14,
                        ),
                    ],
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago,
                            hour=22,
                            minute=45,
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=1
                        ),
                        ActivityType.WORK,
                    ],
                ],
            )
            day_start = get_date(how_many_days_ago)
            regulatory_alert = self._get_alert(day_start=day_start)

            self.assertIsNotNone(regulatory_alert)
            extra_info = regulatory_alert.extra
            self.assertEqual(extra_info["sanction_code"], NATINF_35187)
            self.assertFalse(extra_info["not_enough_break"])
            self.assertTrue(extra_info["too_much_uninterrupted_work_time"])

    def test_min_work_day_break_by_employee_failure(self):
        # freeze date out of clock change day to avoid errors when it happens
        with freeze_time(date(2025, 4, 5)):
            how_many_days_ago = 2

            self._log_and_validate_mission(
                mission_name="9h30 work with 30m break",
                submitter=self.employee,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=15),
                        get_time(
                            how_many_days_ago=how_many_days_ago,
                            hour=22,
                            minute=15,
                        ),
                    ],
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago,
                            hour=22,
                            minute=45,
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=1
                        ),
                        ActivityType.WORK,
                    ],
                ],
            )
            day_start = get_date(how_many_days_ago)
            regulatory_alert = self._get_alert(day_start=day_start)

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
            self.assertEqual(extra_info["sanction_code"], NATINF_35187)

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
        regulatory_alert = self._get_alert(day_start=day_start)

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
        self.assertEqual(extra_info["sanction_code"], NATINF_35187)

    def test_min_work_day_break_on_two_days(self):
        # freeze date out of clock change day to avoid errors when it happens
        with freeze_time(date(2025, 4, 5)):
            how_many_days_ago = 2

            self._log_and_validate_mission(
                mission_name="",
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
            regulatory_alert = self._get_alert(day_start=day_start)

            self.assertIsNone(regulatory_alert)
