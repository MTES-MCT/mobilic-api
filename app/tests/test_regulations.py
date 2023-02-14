import json
from datetime import date, datetime
from unittest.mock import patch

from app import app, db
from app.domain import regulations
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.regulations_utils import HOUR, MINUTE
from app.helpers.submitter_type import SubmitterType
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
        company = self.company
        employee = self.employee
        how_many_days_ago = 3

        mission = Mission(
            name="8h drive J",
            company=company,
            reception_time=datetime.now(),
            submitter=employee,
        )
        db.session.add(mission)

        mission_next_day = Mission(
            name="8h drive J+1",
            company=company,
            reception_time=datetime.now(),
            submitter=employee,
        )
        db.session.add(mission_next_day)

        mission_last_day = Mission(
            name="8h drive J+2",
            company=company,
            reception_time=datetime.now(),
            submitter=employee,
        )
        db.session.add(mission_last_day)

        with AuthenticatedUserContext(user=employee):
            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago, hour=23),
                start_time=get_time(how_many_days_ago, hour=18),
                end_time=get_time(how_many_days_ago, hour=23),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission_next_day,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=15),
                start_time=get_time(how_many_days_ago - 1, hour=4),
                end_time=get_time(how_many_days_ago - 1, hour=6),
            )

            validate_mission(
                submitter=employee, mission=mission_next_day, for_user=employee
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission_last_day,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 2, hour=15),
                start_time=get_time(how_many_days_ago - 2, hour=4),
                end_time=get_time(how_many_days_ago - 2, hour=10),
            )

            validate_mission(
                submitter=employee, mission=mission_last_day, for_user=employee
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
        company = self.company
        employee = self.employee
        how_many_days_ago = 3

        mission = Mission(
            name="8h drive J",
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
                reception_time=get_time(how_many_days_ago, hour=22),
                start_time=get_time(how_many_days_ago, hour=18),
                end_time=get_time(how_many_days_ago, hour=21),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago, hour=23),
                start_time=get_time(how_many_days_ago, hour=22),
                end_time=get_time(how_many_days_ago, hour=23),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=15),
                start_time=get_time(how_many_days_ago - 1, hour=4),
                end_time=get_time(how_many_days_ago - 1, hour=8),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
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
        how_many_days_ago = 3

        mission = Mission(
            name="8h drive J",
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
                reception_time=get_time(how_many_days_ago, hour=22),
                start_time=get_time(how_many_days_ago, hour=18),
                end_time=get_time(how_many_days_ago, hour=19),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=15),
                start_time=get_time(how_many_days_ago - 1, hour=4),
                end_time=get_time(how_many_days_ago - 1, hour=8, minute=1),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=23),
                start_time=get_time(how_many_days_ago - 1, hour=22),
                end_time=get_time(how_many_days_ago - 1, hour=23),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
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
            get_time(how_many_days_ago, hour=18),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["breach_period_end"]),
            get_time(how_many_days_ago - 1, hour=18),
        )
        self.assertEqual(
            extra_info["breach_period_max_break_in_seconds"],
            10 * HOUR - 1 * MINUTE,
        )

    def test_min_daily_rest_by_employee_failure_only_one_day(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 3

        mission = Mission(
            name="8h drive J",
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
                reception_time=get_time(how_many_days_ago - 1, hour=12),
                start_time=get_time(how_many_days_ago - 1, hour=6),
                end_time=get_time(how_many_days_ago - 1, hour=12),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=21),
                start_time=get_time(how_many_days_ago - 1, hour=14),
                end_time=get_time(how_many_days_ago - 1, hour=21),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 2, hour=20),
                start_time=get_time(how_many_days_ago - 2, hour=8),
                end_time=get_time(how_many_days_ago - 2, hour=20),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
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

    def test_min_daily_rest_by_employee_failure(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 2

        # GIVEN
        mission = Mission(
            name="15h drive with 2 groups",
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
                start_time=get_time(how_many_days_ago, hour=13),
                end_time=get_time(how_many_days_ago, hour=19),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=5),
                start_time=get_time(how_many_days_ago, hour=20),
                end_time=get_time(how_many_days_ago - 1, hour=5),
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

    def test_max_work_day_time_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 2

        mission = Mission(
            name="Transfer & night work tarification but not legislation",
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
                type=ActivityType.TRANSFER,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago, hour=5),
                start_time=get_time(how_many_days_ago, hour=3),
                end_time=get_time(how_many_days_ago, hour=5),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago, hour=16),
                start_time=get_time(how_many_days_ago, hour=5),
                end_time=get_time(how_many_days_ago, hour=16),
            )

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

    def test_max_work_day_time_by_employee_failure(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 2

        mission = Mission(
            name="3h work (night) + 8h drive",
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
                type=ActivityType.WORK,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago, hour=7),
                start_time=get_time(how_many_days_ago, hour=4),
                end_time=get_time(how_many_days_ago, hour=7),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago, hour=16),
                start_time=get_time(how_many_days_ago, hour=8),
                end_time=get_time(how_many_days_ago, hour=16),
            )

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

    def test_max_work_day_time_by_admin_failure(self):
        company = self.company
        employee = self.employee
        admin = self.admin
        how_many_days_ago = 2

        mission = Mission(
            name="3h work (night) + 10h drive",
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
                type=ActivityType.WORK,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago, hour=7),
                start_time=get_time(how_many_days_ago, hour=4),
                end_time=get_time(how_many_days_ago, hour=7),
            )
            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago, hour=17),
                start_time=get_time(how_many_days_ago, hour=7),
                end_time=get_time(how_many_days_ago, hour=17),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        with AuthenticatedUserContext(user=admin):
            validate_mission(
                submitter=admin, mission=mission, for_user=employee
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

    def test_min_work_day_break_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 2

        mission = Mission(
            name="8h30 work with 30m break",
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
                reception_time=get_time(how_many_days_ago, hour=23, minute=14),
                start_time=get_time(how_many_days_ago, hour=17),
                end_time=get_time(how_many_days_ago, hour=23, minute=14),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=2),
                start_time=get_time(how_many_days_ago, hour=23, minute=45),
                end_time=get_time(how_many_days_ago - 1, hour=2),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
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

    def test_min_work_day_break_by_employee_failure(self):
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
                reception_time=get_time(how_many_days_ago, hour=23, minute=15),
                start_time=get_time(how_many_days_ago, hour=16),
                end_time=get_time(how_many_days_ago, hour=23, minute=15),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=2),
                start_time=get_time(how_many_days_ago, hour=23, minute=45),
                end_time=get_time(how_many_days_ago - 1, hour=2),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
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
            get_time(how_many_days_ago, hour=16),
        )
        self.assertEqual(
            datetime.fromisoformat(extra_info["work_range_end"]),
            get_time(how_many_days_ago - 1, hour=2),
        )

    def test_max_uninterrupted_work_time_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 2

        mission = Mission(
            name="5h15 drive - 30m pause - 2h15 work",
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
                reception_time=get_time(how_many_days_ago, hour=23, minute=15),
                start_time=get_time(how_many_days_ago, hour=18),
                end_time=get_time(how_many_days_ago, hour=23, minute=15),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=2),
                start_time=get_time(how_many_days_ago, hour=23, minute=45),
                end_time=get_time(how_many_days_ago - 1, hour=2),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
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
        company = self.company
        employee = self.employee
        how_many_days_ago = 2

        mission = Mission(
            name="6h15 drive - 30m pause - 2h15 work",
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
                reception_time=get_time(how_many_days_ago, hour=23, minute=15),
                start_time=get_time(how_many_days_ago, hour=17),
                end_time=get_time(how_many_days_ago, hour=23, minute=15),
            )

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=2),
                start_time=get_time(how_many_days_ago, hour=23, minute=45),
                end_time=get_time(how_many_days_ago - 1, hour=2),
            )

            validate_mission(
                submitter=employee, mission=mission, for_user=employee
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
        company = self.company
        employee = self.employee

        NB_WEEKS = 3
        missions = []
        for i in range(NB_WEEKS):
            mission = Mission(
                name=f"mission #{i}",
                company=company,
                reception_time=datetime.now(),
                submitter=employee,
            )
            db.session.add(mission)
            missions.append(mission)

        with AuthenticatedUserContext(user=employee):
            for i in range(NB_WEEKS):
                how_many_days_ago = 3 + i * 7
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=missions[i],
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=get_time(
                        how_many_days_ago, hour=23, minute=15
                    ),
                    start_time=get_time(how_many_days_ago, hour=17),
                    end_time=get_time(how_many_days_ago, hour=23, minute=15),
                )
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=missions[i],
                    type=ActivityType.WORK,
                    switch_mode=False,
                    reception_time=get_time(how_many_days_ago - 1, hour=2),
                    start_time=get_time(how_many_days_ago, hour=23, minute=45),
                    end_time=get_time(how_many_days_ago - 1, hour=2),
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
