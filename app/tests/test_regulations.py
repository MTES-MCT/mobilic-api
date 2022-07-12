from datetime import datetime, timedelta
from flask.ctx import AppContext
import json

from app import app, db
from app.domain import regulations
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.submitter_type import SubmitterType
from app.models import Mission, MissionEnd
from app.models.activity import ActivityType
from app.models.regulation_day import RegulationDay
from app.models.regulation_check import RegulationCheck, RegulationCheckType
from app.models.regulation_week import RegulationWeek
from app.models.user import User
from app.seed.factories import CompanyFactory, EmploymentFactory, UserFactory
from app.seed.helpers import AuthenticatedUserContext, get_date, get_time
from app.tests import BaseTest

ADMIN_EMAIL = "admin@email.com"
EMPLOYEE_EMAIL = "employee@email.com"


class TestRegulations(BaseTest):
    def setUp(self):
        super().setUp()

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

    def test_min_daily_rest_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 10

        # GIVEN
        mission = Mission(
            name="6h drive",
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
                reception_time=get_time(how_many_days_ago, hour=13),
                start_time=get_time(how_many_days_ago, hour=7),
                end_time=get_time(how_many_days_ago, hour=13),
            )

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago, hour=13),
                    user=employee,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.EMPLOYEE
        )

        # THEN
        regulation_day = RegulationDay.query.filter(
            RegulationDay.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationDay.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulationDay.day == day_start,
            RegulationDay.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulation_day)
        self.assertEqual(regulation_day.success, True)

    def test_min_daily_rest_by_employee_failure(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 12

        # GIVEN
        mission = Mission(
            name="16h drive",
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
                reception_time=get_time(how_many_days_ago - 1, hour=1),
                start_time=get_time(how_many_days_ago, hour=9),
                end_time=get_time(how_many_days_ago - 1, hour=1),
            )

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago - 1, hour=1),
                    user=employee,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.EMPLOYEE
        )

        # THEN
        regulation_day = RegulationDay.query.filter(
            RegulationDay.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationDay.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulationDay.day == day_start,
            RegulationDay.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulation_day)
        self.assertEqual(regulation_day.success, False)

    def test_max_work_day_time_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 14

        # GIVEN
        mission = Mission(
            name="3h transfer + 10h drive (day)",
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

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago, hour=17),
                    user=employee,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.EMPLOYEE
        )

        # THEN
        regulation_day = RegulationDay.query.filter(
            RegulationDay.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationDay.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulationDay.day == day_start,
            RegulationDay.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulation_day)
        self.assertEqual(regulation_day.success, True)
        extra_info = json.loads(regulation_day.extra)
        self.assertEqual(extra_info["night_work"], False)
        self.assertIsNotNone(extra_info["max_time_in_hours"])

    def test_max_work_day_time_by_employee_failure(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 16

        # GIVEN
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
                reception_time=get_time(how_many_days_ago, hour=15),
                start_time=get_time(how_many_days_ago, hour=7),
                end_time=get_time(how_many_days_ago, hour=15),
            )

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago, hour=15),
                    user=employee,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.EMPLOYEE
        )

        # THEN
        regulation_day = RegulationDay.query.filter(
            RegulationDay.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationDay.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulationDay.day == day_start,
            RegulationDay.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulation_day)
        self.assertEqual(regulation_day.success, False)
        extra_info = json.loads(regulation_day.extra)
        self.assertEqual(extra_info["night_work"], True)
        self.assertIsNotNone(extra_info["max_time_in_hours"])

    def test_max_work_day_time_by_admin_failure(self):
        company = self.company
        employee = self.employee
        admin = self.admin
        how_many_days_ago = 18

        # GIVEN
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

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago, hour=17),
                    user=employee,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        with AuthenticatedUserContext(user=admin):
            validate_mission(
                submitter=admin, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.ADMIN
        )

        # THEN
        regulation_day = RegulationDay.query.filter(
            RegulationDay.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationDay.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulationDay.day == day_start,
            RegulationDay.submitter_type == SubmitterType.ADMIN,
        ).one_or_none()
        self.assertIsNotNone(regulation_day)
        self.assertEqual(regulation_day.success, False)
        extra_info = json.loads(regulation_day.extra)
        self.assertEqual(extra_info["night_work"], True)
        self.assertIsNotNone(extra_info["max_time_in_hours"])

    def test_min_work_day_break_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 22

        # GIVEN
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

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago - 1, hour=2),
                    user=employee,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.EMPLOYEE
        )

        # THEN
        regulation_day = RegulationDay.query.filter(
            RegulationDay.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationDay.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
            ),
            RegulationDay.day == day_start,
            RegulationDay.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulation_day)
        self.assertEqual(regulation_day.success, True)

    def test_min_work_day_break_by_employee_failure(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 22

        # GIVEN
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

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago - 1, hour=2),
                    user=employee,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.EMPLOYEE
        )

        # THEN
        regulation_day = RegulationDay.query.filter(
            RegulationDay.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationDay.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
            ),
            RegulationDay.day == day_start,
            RegulationDay.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulation_day)
        self.assertEqual(regulation_day.success, False)

    def test_max_uninterrupted_work_time_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 24

        # GIVEN
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

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago - 1, hour=2),
                    user=employee,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.EMPLOYEE
        )

        # THEN
        regulation_day = RegulationDay.query.filter(
            RegulationDay.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationDay.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME
            ),
            RegulationDay.day == day_start,
            RegulationDay.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulation_day)
        self.assertEqual(regulation_day.success, True)

    def test_max_uninterrupted_work_time_by_employee_failure(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 26

        # GIVEN
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

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago - 1, hour=2),
                    user=employee,
                    mission=mission,
                )
            )
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.EMPLOYEE
        )

        # THEN
        regulation_day = RegulationDay.query.filter(
            RegulationDay.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationDay.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME
            ),
            RegulationDay.day == day_start,
            RegulationDay.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulation_day)
        self.assertEqual(regulation_day.success, False)
