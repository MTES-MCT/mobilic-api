from datetime import date, timedelta

from app.domain.regulations_per_week import NATINF_11289
from app.helpers.regulations_utils import HOUR, MINUTE
from app.helpers.submitter_type import SubmitterType
from app.helpers.time import get_first_day_of_week
from app.models import RegulatoryAlert, User, RegulationCheck
from app.models.regulation_check import RegulationCheckType
from app.seed.helpers import (
    get_time,
)
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestMaximumWorkCalendarWeek(RegulationsTest):
    def test_maximum_work_calendar_week_trv(self):

        self.convert_employee_to_trv()
        first_day_last_week = get_first_day_of_week(date.today()) - timedelta(
            days=7
        )
        last_week_start_offset = (date.today() - first_day_last_week).days

        work_periods = []
        for i in reversed(range(5)):
            day_offset = last_week_start_offset - i
            work_periods.append(
                [
                    get_time(how_many_days_ago=day_offset, hour=7),
                    get_time(how_many_days_ago=day_offset, hour=12),
                ]
            )
            if i == 4:
                work_periods.append(
                    [
                        get_time(how_many_days_ago=day_offset, hour=13),
                        get_time(how_many_days_ago=day_offset, hour=15),
                    ]
                )
            else:
                work_periods.append(
                    [
                        get_time(how_many_days_ago=day_offset, hour=13),
                        get_time(how_many_days_ago=day_offset, hour=18),
                    ]
                )

        self._log_and_validate_mission(
            mission_name="debut de semaine, 47h - ok",
            submitter=self.employee,
            work_periods=work_periods,
        )

        # No alert. 47h is fine for TRV
        regulatory_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
        ).all()
        self.assertEqual(0, len(regulatory_alerts))

        # getting past the 48h limit
        self._log_and_validate_mission(
            mission_name="one more",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=last_week_start_offset - 4, hour=16
                    ),
                    get_time(
                        how_many_days_ago=last_week_start_offset - 4,
                        hour=17,
                        minute=30,
                    ),
                ]
            ],
        )

        # There should be an alert
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_IN_CALENDAR_WEEK
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()

        self.assertIsNotNone(regulatory_alert)
        self.assertEqual(regulatory_alert.day, first_day_last_week)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["sanction_code"], NATINF_11289)
        self.assertEqual(
            extra_info["work_duration_in_seconds"], 48 * HOUR + 30 * MINUTE
        )

    def test_maximum_work_calendar_week_trm_short_distance(self):

        self.convert_employee_to_trm_short_distance()
        first_day_last_week = get_first_day_of_week(date.today()) - timedelta(
            days=7
        )
        last_week_start_offset = (date.today() - first_day_last_week).days

        work_periods = []
        for i in reversed(range(6)):
            day_offset = last_week_start_offset - i
            if i == 5:
                work_periods.append(
                    [
                        get_time(how_many_days_ago=day_offset, hour=7),
                        get_time(how_many_days_ago=day_offset, hour=8),
                    ]
                )
            else:
                work_periods.append(
                    [
                        get_time(how_many_days_ago=day_offset, hour=7),
                        get_time(how_many_days_ago=day_offset, hour=12),
                    ]
                )
                work_periods.append(
                    [
                        get_time(how_many_days_ago=day_offset, hour=13),
                        get_time(how_many_days_ago=day_offset, hour=18),
                    ]
                )

        self._log_and_validate_mission(
            mission_name="debut de semaine, 10/10/10/10/10/1 => 51h - ok",
            submitter=self.employee,
            work_periods=work_periods,
        )

        # No alert. 51h is fine for TRM Short Distance
        regulatory_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
        ).all()
        self.assertEqual(0, len(regulatory_alerts))

        # getting past the 52h limit
        self._log_and_validate_mission(
            mission_name="one more",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=last_week_start_offset - 5, hour=16
                    ),
                    get_time(
                        how_many_days_ago=last_week_start_offset - 5,
                        hour=17,
                        minute=30,
                    ),
                ]
            ],
        )

        # There should be an alert
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_IN_CALENDAR_WEEK
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()

        self.assertIsNotNone(regulatory_alert)
        self.assertEqual(regulatory_alert.day, first_day_last_week)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["sanction_code"], NATINF_11289)
        self.assertEqual(
            extra_info["work_duration_in_seconds"], 52 * HOUR + 30 * MINUTE
        )
