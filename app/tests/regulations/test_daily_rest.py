from datetime import datetime, date
from freezegun import freeze_time

from app.domain.regulations_per_day import NATINF_20525
from app.helpers.regulations_utils import HOUR, MINUTE
from app.helpers.submitter_type import SubmitterType
from app.helpers.time import FR_TIMEZONE
from app.models import User, RegulatoryAlert
from app.models.regulation_check import RegulationCheckType, RegulationCheck
from app.seed.helpers import get_time, get_date
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL
from unittest import skip


class TestDailyRest(RegulationsTest):
    def test_min_daily_rest_by_employee_success(self):
        how_many_days_ago = 3

        self._log_and_validate_mission(
            mission_name="5h drive J",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=18),
                    get_time(how_many_days_ago=how_many_days_ago, hour=23),
                ],
            ],
        )
        self._log_and_validate_mission(
            mission_name="2h drive J+1",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=4),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=6),
                ],
            ],
        )
        self._log_and_validate_mission(
            mission_name="6h drive J+2",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago - 2, hour=4),
                    get_time(how_many_days_ago=how_many_days_ago - 2, hour=10),
                ],
            ],
        )
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)

    def test_min_daily_rest_by_employee_success_exact_min_rest(self):
        how_many_days_ago = 3

        self._log_and_validate_mission(
            mission_name="3 + 1 + 4 on two days",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=18),
                    get_time(how_many_days_ago=how_many_days_ago, hour=21),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=22),
                    get_time(how_many_days_ago=how_many_days_ago, hour=23),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=4),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=8),
                ],
            ],
        )
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)

    def test_min_daily_rest_by_employee_failure_one_minute(self):
        employee = self.employee
        how_many_days_ago = 4

        self._log_and_validate_mission(
            mission_name="Missing one minute break",
            submitter=employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=18),
                    get_time(how_many_days_ago=how_many_days_ago, hour=19),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=4),
                    get_time(
                        how_many_days_ago=how_many_days_ago - 1,
                        hour=8,
                        minute=1,
                    ),
                ],
            ],
        )
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["min_daily_break_in_hours"], 10)
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago, hour=18, tz=FR_TIMEZONE),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago - 1, hour=18, tz=FR_TIMEZONE),
        )
        self.assertEqual(
            extra_info["breach_period_max_break_in_seconds"],
            10 * HOUR - 1 * MINUTE,
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_20525)

    def test_min_daily_rest_simple_case(self):
        how_many_days_ago = 4

        self._log_and_validate_mission(
            mission_name="4h drive / 9h45 break / drive",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=4),
                    get_time(how_many_days_ago=how_many_days_ago, hour=8),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=17, minute=45
                    ),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=3),
                ],
            ],
        )
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["min_daily_break_in_hours"], 10)
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago, hour=4),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago - 1, hour=4),
        )
        self.assertEqual(
            extra_info["breach_period_max_break_in_seconds"],
            9 * HOUR + 45 * MINUTE,
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_20525)

    def test_min_daily_rest_lot_of_activities(self):
        how_many_days_ago = 4

        work_periods = []
        for start_hour in range(4, 12, 2):
            work_periods.append(
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=start_hour
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago,
                        hour=start_hour + 1,
                    ),
                ]
            )

        work_periods.append(
            [
                get_time(
                    how_many_days_ago=how_many_days_ago, hour=16, minute=10
                ),
                get_time(how_many_days_ago=how_many_days_ago, hour=17),
            ]
        )
        work_periods.append(
            [
                get_time(how_many_days_ago=how_many_days_ago, hour=18),
                get_time(how_many_days_ago=how_many_days_ago - 1, hour=3),
            ]
        )

        self._log_and_validate_mission(
            mission_name="Several 1h drives, 5h10 break then long drive",
            submitter=self.employee,
            work_periods=work_periods,
        )

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["min_daily_break_in_hours"], 10)
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago, hour=4),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago - 1, hour=4),
        )
        self.assertEqual(
            extra_info["breach_period_max_break_in_seconds"],
            5 * HOUR + 10 * MINUTE,
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_20525)

    @skip("TODO: remove after 30/10/2025")
    def test_min_daily_rest_by_employee_failure_only_one_day(self):
        employee = self.employee
        how_many_days_ago = 3

        self._log_and_validate_mission(
            mission_name="6h drive / 2h break / 7h drive / 11h break / 12h drive",
            submitter=employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=6),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=12),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=14),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=21),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago - 2, hour=8),
                    get_time(how_many_days_ago=how_many_days_ago - 2, hour=20),
                ],
            ],
        )

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago - 1, hour=6),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago - 2, hour=6),
        )
        self.assertEqual(
            extra_info["breach_period_max_break_in_seconds"], 9 * HOUR
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_20525)

    @skip("TODO: remove after 30/10/2025")
    def test_min_daily_rest_by_employee_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="6h drive / 1h break / 9h drive",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=13),
                    get_time(how_many_days_ago=how_many_days_ago, hour=19),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=20),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=5),
                ],
            ],
        )
        day_start = get_date(how_many_days_ago)

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago, hour=13),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago - 1, hour=13),
        )
        self.assertEqual(
            extra_info["breach_period_max_break_in_seconds"], 8 * HOUR
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_20525)

    @skip("TODO: remove after 30/10/2025")
    def test_min_daily_rest_by_employee_failure_complex_case(self):
        self._log_and_validate_mission(
            mission_name="4hD/30mB/4hD/15mB/3hD/5h15B/4hD/3hB/7hD",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=2, hour=8),
                    get_time(how_many_days_ago=2, hour=12),
                ],
                [
                    get_time(how_many_days_ago=2, hour=12, minute=30),
                    get_time(how_many_days_ago=2, hour=16, minute=30),
                ],
                [
                    get_time(how_many_days_ago=2, hour=16, minute=45),
                    get_time(how_many_days_ago=2, hour=19, minute=45),
                ],
                [
                    get_time(how_many_days_ago=1, hour=1),
                    get_time(how_many_days_ago=1, hour=5),
                ],
                [
                    get_time(how_many_days_ago=1, hour=8),
                    get_time(how_many_days_ago=1, hour=15),
                ],
            ],
        )
        day_start = get_date(2)
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
            RegulatoryAlert.day == day_start,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = regulatory_alert.extra
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago=2, hour=8),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago=1, hour=8),
        )
        self.assertEqual(
            extra_info["breach_period_max_break_in_seconds"],
            5 * HOUR + 15 * MINUTE,
        )

    @skip("TODO: remove after 30/10/2025")
    def test_min_daily_rest_by_employee_failure_complex_case_double_alert(
        self,
    ):
        self._log_and_validate_mission(
            mission_name="4hD/30mB/4hD/15mB/3hD/5h15B/4hD/3hB/7h30D",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=2, hour=8),
                    get_time(how_many_days_ago=2, hour=12),
                ],
                [
                    get_time(how_many_days_ago=2, hour=12, minute=30),
                    get_time(how_many_days_ago=2, hour=16, minute=30),
                ],
                [
                    get_time(how_many_days_ago=2, hour=16, minute=45),
                    get_time(how_many_days_ago=2, hour=19, minute=45),
                ],
                [
                    get_time(how_many_days_ago=1, hour=1),
                    get_time(how_many_days_ago=1, hour=5),
                ],
                [
                    get_time(how_many_days_ago=1, hour=8),
                    get_time(how_many_days_ago=1, hour=15, minute=30),
                ],
            ],
        )
        regulatory_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(2, len(regulatory_alerts))
        extra_info = regulatory_alerts[1].extra
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago=1, hour=1),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago=0, hour=1),
        )
        self.assertEqual(
            extra_info["breach_period_max_break_in_seconds"],
            9 * HOUR + 30 * MINUTE,
        )

    def test_daily_rest_no_rest_extra_data(self):
        how_many_days_ago = 5
        self._log_and_validate_mission(
            mission_name="Longue mission",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=6),
                    get_time(how_many_days_ago=how_many_days_ago - 2, hour=20),
                ],
            ],
        )
        regulatory_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(3, len(regulatory_alerts))

        extras = [ra.extra for ra in regulatory_alerts]
        self.assertEqual(
            0, extras[0].get("breach_period_max_break_in_seconds")
        )
        self.assertEqual(
            0, extras[1].get("breach_period_max_break_in_seconds")
        )
        self.assertEqual(
            0, extras[2].get("breach_period_max_break_in_seconds")
        )

    def test_night_worker(self):
        # freeze date out of clock change day to avoid errors when it happens
        with freeze_time(date(2025, 4, 5)):
            how_many_days_ago = 3
            self._log_and_validate_mission(
                mission_name="Mission de nuit",
                submitter=self.employee,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=20),
                        get_time(how_many_days_ago=how_many_days_ago, hour=23),
                    ],
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=1
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=5
                        ),
                    ],
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=7
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=11
                        ),
                    ],
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=13
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=19
                        ),
                    ],
                ],
            )
            regulatory_alerts = RegulatoryAlert.query.filter(
                RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
                RegulatoryAlert.regulation_check.has(
                    RegulationCheck.type
                    == RegulationCheckType.MINIMUM_DAILY_REST
                ),
                RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
            ).all()
            self.assertEqual(2, len(regulatory_alerts))

            extras = [ra.extra for ra in regulatory_alerts]
            self.assertEqual(
                2 * HOUR, extras[0].get("breach_period_max_break_in_seconds")
            )
            self.assertEqual(
                6 * HOUR, extras[1].get("breach_period_max_break_in_seconds")
            )

    def test_night_worker_on_clock_change(self):
        # changed clock on night from 29th to 30th March 2025
        with freeze_time(date(2025, 4, 1)):
            how_many_days_ago = 3
            self._log_and_validate_mission(
                mission_name="Mission de nuit",
                submitter=self.employee,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=20),
                        get_time(how_many_days_ago=how_many_days_ago, hour=23),
                    ],
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=1
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=5
                        ),
                    ],
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=7
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=11
                        ),
                    ],
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=13
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=19
                        ),
                    ],
                ],
            )
            regulatory_alerts = RegulatoryAlert.query.filter(
                RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
                RegulatoryAlert.regulation_check.has(
                    RegulationCheck.type
                    == RegulationCheckType.MINIMUM_DAILY_REST
                ),
                RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
            ).all()
            self.assertEqual(2, len(regulatory_alerts))

            extras = [ra.extra for ra in regulatory_alerts]
            self.assertEqual(
                2 * HOUR, extras[0].get("breach_period_max_break_in_seconds")
            )
            # +1 hour because of clock change
            self.assertEqual(
                7 * HOUR, extras[1].get("breach_period_max_break_in_seconds")
            )
