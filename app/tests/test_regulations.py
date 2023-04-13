import json
from datetime import date, datetime
import unittest
from unittest.mock import patch

from app import app, db
from app.domain import regulations
from app.domain.log_activities import log_activity
from app.domain.regulations_per_day import (
    NATINF_11292,
    NATINF_32083,
    SANCTION_CODE,
    NATINF_20525,
)
from app.domain.regulations_per_week import NATINF_13152
from app.domain.validation import validate_mission
from app.helpers.regulations_utils import HOUR, MINUTE
from app.helpers.submitter_type import SubmitterType
from app.helpers.time import LOCAL_TIMEZONE, FR_TIMEZONE
from app.models import Mission
from app.models.activity import ActivityType
from app.models.regulation_check import (
    RegulationCheck,
    RegulationCheckType,
    UnitType,
)
from app.models.regulation_computation import RegulationComputation
from app.models.regulatory_alert import RegulatoryAlert
from app.models.user import User
from app.seed.factories import CompanyFactory, EmploymentFactory, UserFactory
from app.seed.helpers import (
    AuthenticatedUserContext,
    get_date,
    get_datetime_tz,
    get_time,
)
from app.services.get_regulation_checks import (
    RegulationCheckData,
)
from app.tests import BaseTest
from dateutil.tz import gettz
from flask.ctx import AppContext

from app.tests.helpers import (
    init_regulation_checks_data,
    insert_regulation_check,
)

ADMIN_EMAIL = "admin@email.com"
EMPLOYEE_EMAIL = "employee@email.com"


class TestRegulations(BaseTest):
    def setUp(self):
        super().setUp()

        init_regulation_checks_data()

        company = CompanyFactory.create(
            usual_name="Company Name", siren="1122334", allow_transfers=True
        )

        admin = UserFactory.create(
            email=ADMIN_EMAIL,
            password="password",
            first_name="Admin",
            last_name="Admin",
        )
        EmploymentFactory.create(
            company=company, submitter=admin, user=admin, has_admin_rights=True
        )

        employee = UserFactory.create(
            email=EMPLOYEE_EMAIL,
            password="password",
        )
        EmploymentFactory.create(
            company=company,
            submitter=admin,
            user=employee,
            has_admin_rights=False,
        )

        self.company = company
        self.admin = admin
        self.employee = employee
        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _log_and_validate_mission(
        self, mission_name, company, reception_time, submitter, work_periods
    ):
        mission = Mission(
            name=mission_name,
            company=company,
            reception_time=reception_time,
            submitter=submitter,
        )
        db.session.add(mission)
        db.session.commit()

        with AuthenticatedUserContext(user=submitter):
            for work_period in work_periods:
                log_activity(
                    submitter=submitter,
                    user=submitter,
                    mission=mission,
                    type=work_period[2]
                    if len(work_period) >= 3
                    else ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=work_period[1],
                    start_time=work_period[0],
                    end_time=work_period[1],
                )
            validate_mission(
                submitter=submitter, mission=mission, for_user=submitter
            )
        return mission

    def test_no_activity_all_success(self):
        employee = self.employee
        how_many_days_ago = 2

        day_start = get_date(how_many_days_ago)
        day_end = get_date(how_many_days_ago - 1)

        # WHEN
        regulations.compute_regulations(
            employee, day_start, day_end, SubmitterType.EMPLOYEE
        )

        # THEN
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)

        computation_done = RegulationComputation.query.filter(
            RegulationComputation.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationComputation.day == day_start,
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(computation_done)

    def test_min_daily_rest_by_employee_success(self):
        how_many_days_ago = 3

        self._log_and_validate_mission(
            mission_name="5h drive J",
            company=self.company,
            reception_time=datetime.now(),
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
            company=self.company,
            reception_time=datetime.now(),
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
            company=self.company,
            reception_time=datetime.now(),
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
            company=self.company,
            reception_time=datetime.now(),
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
        company = self.company
        employee = self.employee
        how_many_days_ago = 4

        self._log_and_validate_mission(
            mission_name="Missing one minute break",
            company=company,
            reception_time=datetime.now(),
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
                [
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=22),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=23),
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
        extra_info = json.loads(regulatory_alert.extra)
        self.assertEqual(extra_info["min_daily_break_in_hours"], 10)
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago, hour=18, tz=LOCAL_TIMEZONE),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago - 1, hour=18, tz=LOCAL_TIMEZONE),
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
            company=self.company,
            reception_time=datetime.now(),
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
        extra_info = json.loads(regulatory_alert.extra)
        self.assertEqual(extra_info["min_daily_break_in_hours"], 10)
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago, hour=4, tz=LOCAL_TIMEZONE),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago - 1, hour=4, tz=LOCAL_TIMEZONE),
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
            company=self.company,
            reception_time=datetime.now(),
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
        extra_info = json.loads(regulatory_alert.extra)
        self.assertEqual(extra_info["min_daily_break_in_hours"], 10)
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_start"]),
            get_time(how_many_days_ago, hour=4, tz=LOCAL_TIMEZONE),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago - 1, hour=4, tz=LOCAL_TIMEZONE),
        )
        self.assertEqual(
            extra_info["breach_period_max_break_in_seconds"],
            5 * HOUR + 10 * MINUTE,
        )
        self.assertEqual(extra_info["sanction_code"], NATINF_20525)

    def test_min_daily_rest_by_employee_failure_only_one_day(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 3

        self._log_and_validate_mission(
            mission_name="6h drive / 2h break / 7h drive / 11h break / 12h drive",
            company=company,
            reception_time=datetime.now(),
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
        extra_info = json.loads(regulatory_alert.extra)
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

    def test_min_daily_rest_by_employee_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="6h drive / 1h break / 9h drive",
            company=self.company,
            reception_time=datetime.now(),
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
        extra_info = json.loads(regulatory_alert.extra)
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

    def test_min_daily_rest_by_employee_failure_complex_case(self):
        self._log_and_validate_mission(
            mission_name="4hD/30mB/4hD/15mB/3hD/5h15B/4hD/3hB/7hD",
            company=self.company,
            reception_time=datetime.now(),
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
        extra_info = json.loads(regulatory_alert.extra)
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

    def test_min_daily_rest_by_employee_failure_complex_case_double_alert(
        self,
    ):
        self._log_and_validate_mission(
            mission_name="4hD/30mB/4hD/15mB/3hD/5h15B/4hD/3hB/7h30D",
            company=self.company,
            reception_time=datetime.now(),
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
        extra_info = json.loads(regulatory_alerts[1].extra)
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

    def test_max_work_day_time_by_employee_success(self):
        how_many_days_ago = 2
        self._log_and_validate_mission(
            mission_name="Transfer & night work tarification but not legislation",
            company=self.company,
            reception_time=datetime.now(),
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
        day_start = get_date(how_many_days_ago)

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)

    def test_max_work_day_time_by_employee_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="3h work (night) + 8h drive",
            company=self.company,
            reception_time=datetime.now(),
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
        day_start = get_date(how_many_days_ago)

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = json.loads(regulatory_alert.extra)
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
            company=self.company,
            reception_time=datetime.now(),
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

        day_start = get_date(how_many_days_ago)

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = json.loads(regulatory_alert.extra)
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

    def test_max_work_day_time_by_admin_failure(self):
        how_many_days_ago = 2

        mission = self._log_and_validate_mission(
            mission_name="3h work (night) + 10h drive",
            company=self.company,
            reception_time=datetime.now(),
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

        day_start = get_date(how_many_days_ago)

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.ADMIN,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = json.loads(regulatory_alert.extra)
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

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)

    @unittest.skip("Not working properly due to Timezone problem")
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

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = json.loads(regulatory_alert.extra)
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

    def test_max_uninterrupted_work_time_by_employee_success(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="5h15 drive - 30m pause - 2h15 work",
            company=self.company,
            reception_time=datetime.now(),
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

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)

    def test_max_uninterrupted_work_time_by_employee_failure(self):
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="6h15 drive - 30m pause - 2h15 work",
            company=self.company,
            reception_time=datetime.now(),
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

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        extra_info = json.loads(regulatory_alert.extra)
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
        self.assertEqual(extra_info["sanction_code"], SANCTION_CODE)

    def test_use_latest_regulation_check_by_type(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 2

        expired_regulation_data = RegulationCheckData(
            type="minimumDailyRest",
            label="Non-respect(s) du repos quotidien",
            description="Règlementation expirée",
            date_application_start=get_datetime_tz(2018, 1, 1),
            date_application_end=get_datetime_tz(2019, 11, 1),
            regulation_rule="dailyRest",
            variables=None,
            unit=UnitType.DAY,
        )
        insert_regulation_check(expired_regulation_data)

        mission = Mission(
            name="any mission",
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
                reception_time=get_time(how_many_days_ago, hour=19),
                start_time=get_time(how_many_days_ago, hour=4),
                end_time=get_time(how_many_days_ago, hour=19),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(len(regulatory_alert), 1)
        self.assertIsNone(
            regulatory_alert[0].regulation_check.date_application_end
        )

    @patch("app.domain.regulations.compute_regulations_per_day")
    def test_compute_regulations_calls_daily_regulations_for_all_days(
        self, mock_compute_regulations_per_day
    ):
        # GIVEN
        employee = self.employee
        period_start = get_date(how_many_days_ago=18)
        period_end = get_date(how_many_days_ago=3)

        # WHEN
        regulations.compute_regulations(
            employee, period_start, period_end, SubmitterType.EMPLOYEE
        )

        # THEN
        self.assertEqual(mock_compute_regulations_per_day.call_count, 17)

        computations_done = RegulationComputation.query.filter(
            RegulationComputation.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(len(computations_done), 17)

    def test_compute_regulations_per_week_success(self):
        nb_weeks = 3
        for i in range(nb_weeks):
            how_many_days_ago = 3 + i * 7
            self._log_and_validate_mission(
                mission_name=f"mission #{i}",
                company=self.company,
                reception_time=datetime.now(),
                submitter=self.employee,
                work_periods=[
                    [
                        get_time(how_many_days_ago=how_many_days_ago, hour=17),
                        get_time(
                            how_many_days_ago=how_many_days_ago,
                            hour=23,
                            minute=15,
                        ),
                    ],
                    [
                        get_time(
                            how_many_days_ago=how_many_days_ago,
                            hour=23,
                            minute=45,
                        ),
                        get_time(
                            how_many_days_ago=how_many_days_ago - 1, hour=2
                        ),
                        ActivityType.WORK,
                    ],
                ],
            )
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)

    def test_compute_regulations_per_week_too_many_days(self):
        company = self.company
        employee = self.employee

        missions = []
        for i in range(14):
            mission = Mission(
                name=f"Day #{i}",
                company=company,
                reception_time=datetime.now(),
                submitter=employee,
            )
            db.session.add(mission)
            missions.append(mission)

        with AuthenticatedUserContext(user=employee):
            for i in range(14):
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=missions[i],
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=get_datetime_tz(2022, 7, 6 + i, 12),
                    start_time=get_datetime_tz(2022, 7, 6 + i, 7),
                    end_time=get_datetime_tz(2022, 7, 6 + i, 12),
                )
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=missions[i],
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=get_datetime_tz(2022, 7, 6 + i, 17),
                    start_time=get_datetime_tz(2022, 7, 6 + i, 13),
                    end_time=get_datetime_tz(2022, 7, 6 + i, 17),
                )

                validate_mission(
                    submitter=employee, mission=missions[i], for_user=employee
                )

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        self.assertEqual(regulatory_alert.day, date(2022, 7, 11))
        extra_info = json.loads(regulatory_alert.extra)
        self.assertEqual(extra_info["max_nb_days_worked_by_week"], 6)
        self.assertEqual(extra_info["min_weekly_break_in_hours"], 34)
        self.assertTrue(extra_info["too_many_days"])
        self.assertIn("rest_duration_s", extra_info)
        self.assertEqual(extra_info["rest_duration_s"], 14 * HOUR)
        self.assertEqual(extra_info["sanction_code"], NATINF_13152)

    def test_compute_regulations_per_week_not_enough_break(self):
        company = self.company
        employee = self.employee

        missions = []
        for i in range(6):
            mission = Mission(
                name=f"Day #{i}",
                company=company,
                reception_time=datetime.now(),
                submitter=employee,
            )
            db.session.add(mission)
            missions.append(mission)

        mission_final = Mission(
            name=f"Final day",
            company=company,
            reception_time=datetime.now(),
            submitter=employee,
        )
        db.session.add(mission_final)

        with AuthenticatedUserContext(user=employee):
            for i in range(6):
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=missions[i],
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=get_datetime_tz(2022, 7, 18 + i, 12),
                    start_time=get_datetime_tz(2022, 7, 18 + i, 7),
                    end_time=get_datetime_tz(2022, 7, 18 + i, 12),
                )
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=missions[i],
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=get_datetime_tz(2022, 7, 18 + i, 17),
                    start_time=get_datetime_tz(2022, 7, 18 + i, 13),
                    end_time=get_datetime_tz(2022, 7, 18 + i, 17),
                )

                validate_mission(
                    submitter=employee, mission=missions[i], for_user=employee
                )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission_final,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_datetime_tz(2022, 7, 25, 12),
                start_time=get_datetime_tz(2022, 7, 25, 7),
                end_time=get_datetime_tz(2022, 7, 25, 12),
            )
            log_activity(
                submitter=employee,
                user=employee,
                mission=mission_final,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_datetime_tz(2022, 7, 25, 17),
                start_time=get_datetime_tz(2022, 7, 25, 13),
                end_time=get_datetime_tz(2022, 7, 25, 17),
            )

            validate_mission(
                submitter=employee, mission=mission_final, for_user=employee
            )

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK
            ),
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)
        self.assertEqual(regulatory_alert.day, date(2022, 7, 18))
        extra_info = json.loads(regulatory_alert.extra)
        self.assertFalse(extra_info["too_many_days"])
        self.assertEqual(extra_info["rest_duration_s"], 111600)
        self.assertEqual(extra_info["sanction_code"], NATINF_13152)

    def test_max_work_day_time_in_guyana_success(self):
        company = self.company
        admin = self.admin
        how_many_days_ago = 2

        GY_TZ_NAME = "America/Cayenne"
        GY_TIMEZONE = gettz(GY_TZ_NAME)

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

        day_start = get_date(how_many_days_ago)

        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)
