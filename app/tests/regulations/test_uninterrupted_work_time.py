from datetime import datetime

from app.domain.regulations_per_day import NATINF_35187
from app.helpers.regulations_utils import HOUR, MINUTE
from app.helpers.submitter_type import SubmitterType
from app.models import RegulatoryAlert, User
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType, RegulationCheck
from app.seed.helpers import get_time, get_date
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestUninterruptedWorkTime(RegulationsTest):
    def _get_alert(self, day_start):
        return RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.ENOUGH_BREAK
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()

    def test_max_uninterrupted_work_time_by_employee_success(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="5h15 drive - 30m pause - 2h15 work",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=18),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=23, minute=15
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=23, minute=45
                    ),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=2),
                    ActivityType.WORK,
                ],
            ],
        )

        day_start = get_date(how_many_days_ago)
        regulatory_alert = self._get_alert(day_start=day_start)

        self.assertIsNone(regulatory_alert)

    def test_max_uninterrupted_work_time_by_employee_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="6h15 drive - 30m pause - 2h15 work",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=17),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=23, minute=15
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=23, minute=45
                    ),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=1),
                    ActivityType.WORK,
                ],
            ],
        )
        day_start = get_date(how_many_days_ago)
        regulatory_alert = self._get_alert(day_start=day_start)

        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["max_uninterrupted_work_in_hours"], 6)
        self.assertEqual(
            extra_info["longest_uninterrupted_work_in_seconds"],
            6 * HOUR + 15 * MINUTE,
        )
        self.assertEqual(
            datetime.fromisoformat(
                extra_info["longest_uninterrupted_work_start"]
            ),
            get_time(how_many_days_ago, hour=17),
        )
        self.assertEqual(
            datetime.fromisoformat(
                extra_info["longest_uninterrupted_work_end"]
            ),
            get_time(how_many_days_ago, hour=23, minute=15),
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_35187)
        self.assertFalse(extra_info["not_enough_break"])
        self.assertTrue(extra_info["too_much_uninterrupted_work_time"])

    def test_ok_uninterrupted_work_on_two_days(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="Mission on two days",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=19, minute=51
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=21, minute=24
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=21, minute=24
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=0,
                        minute=19,
                    ),
                ],
            ],
        )
        day_start = get_date(how_many_days_ago)
        regulatory_alert = self._get_alert(day_start=day_start)

        self.assertIsNone(regulatory_alert)

    def test_ko_uninterrupted_work_on_two_days(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="Mission on two days",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=18, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=20, minute=0
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=20, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=1,
                        minute=0,
                    ),
                ],
            ],
        )
        day_start = get_date(how_many_days_ago)
        regulatory_alert = self._get_alert(day_start=day_start)

        self.assertIsNotNone(regulatory_alert)

        extra_info = regulatory_alert.extra
        self.assertEqual(
            extra_info["longest_uninterrupted_work_in_seconds"],
            7 * HOUR,
        )
        self.assertEqual(
            datetime.fromisoformat(
                extra_info["longest_uninterrupted_work_start"]
            ),
            get_time(how_many_days_ago, hour=18),
        )
        self.assertEqual(
            datetime.fromisoformat(
                extra_info["longest_uninterrupted_work_end"]
            ),
            get_time(how_many_days_ago - 1, hour=1, minute=0),
        )
        self.assertTrue(extra_info["not_enough_break"])
        self.assertTrue(extra_info["too_much_uninterrupted_work_time"])

    def test_new_regulation_check_triggers_only(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="Long mission",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=3, minute=0
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=14, minute=0
                    ),
                ],
            ],
        )

        new_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.ENOUGH_BREAK
            ),
        ).all()

        self.assertEqual(1, len(new_alerts))
        new_alert = new_alerts[0]
        new_alert_extra = new_alert.extra
        self.assertTrue(new_alert_extra["not_enough_break"])
        self.assertTrue(new_alert_extra["too_much_uninterrupted_work_time"])

        old_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type.in_(
                    [
                        RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME,
                        RegulationCheckType.MINIMUM_WORK_DAY_BREAK,
                    ]
                )
            ),
        ).all()

        self.assertEqual(0, len(old_alerts))
