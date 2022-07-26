import json
from datetime import datetime, timedelta
from unittest.mock import patch

from app import app, db
from app.domain import regulations
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.submitter_type import SubmitterType
from app.models import Mission, MissionEnd
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheck, RegulationCheckType
from app.models.regulatory_alert import RegulatoryAlert
from app.models.user import User
from app.seed.factories import CompanyFactory, EmploymentFactory, UserFactory
from app.seed.helpers import AuthenticatedUserContext, get_date, get_time
from app.services.get_regulation_checks import (
    RegulationCheckData,
    get_regulation_checks,
)
from app.tests import BaseTest
from flask.ctx import AppContext
from sqlalchemy import insert

ADMIN_EMAIL = "admin@email.com"
EMPLOYEE_EMAIL = "employee@email.com"


def insert_regulation_check(regulation_data):
    db.session.execute(
        """
            INSERT INTO regulation_check(
              creation_time,
              type,
              label,
              description,
              date_application_start,
              date_application_end,
              regulation_rule,
              variables
            )
            VALUES
            (
              NOW(),
              :type,
              :label,
              :description,
              :date_application_start,
              :date_application_end,
              :regulation_rule,
              :variables
            )
            """,
        dict(
            type=regulation_data.type,
            label=regulation_data.label,
            description=regulation_data.description,
            date_application_start=regulation_data.date_application_start,
            date_application_end=regulation_data.date_application_end,
            regulation_rule=regulation_data.regulation_rule,
            variables=regulation_data.variables,
        ),
    )


class TestRegulations(BaseTest):
    def setUp(self):
        super().setUp()

        regulation_checks = get_regulation_checks()
        for r in regulation_checks:
            insert_regulation_check(r)

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
        how_many_days_ago = 2

        # GIVEN
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

        with AuthenticatedUserContext(user=employee):
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

            log_activity(
                submitter=employee,
                user=employee,
                mission=mission_next_day,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago - 1, hour=15),
                start_time=get_time(how_many_days_ago - 1, hour=7),
                end_time=get_time(how_many_days_ago - 1, hour=15),
            )

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago - 1, hour=15),
                    user=employee,
                    mission=mission_next_day,
                )
            )
            validate_mission(
                submitter=employee, mission=mission_next_day, for_user=employee
            )

        day_start = get_date(how_many_days_ago)

        # WHEN
        regulations.compute_regulations_per_day(
            employee, day_start, SubmitterType.EMPLOYEE
        )

        # THEN
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(regulatory_alert)

    def test_min_daily_rest_by_employee_failure(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 1

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

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago - 1, hour=5),
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
        regulatory_alert = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(regulatory_alert)

    def test_max_work_day_time_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 1

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
        how_many_days_ago = 1

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
        self.assertIsNotNone(extra_info["max_time_in_hours"])

    def test_max_work_day_time_by_admin_failure(self):
        company = self.company
        employee = self.employee
        admin = self.admin
        how_many_days_ago = 1

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
        self.assertIsNotNone(extra_info["max_time_in_hours"])

    def test_min_work_day_break_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 1

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
        how_many_days_ago = 1

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
        self.assertEqual(extra_info["min_time_in_minutes"], 45)

    def test_max_uninterrupted_work_time_by_employee_success(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 1

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
        how_many_days_ago = 1

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

    def test_use_latest_regulation_check_by_type(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 1

        # GIVEN
        expired_regulation_data = RegulationCheckData(
            type="minimumDailyRest",
            label="Non-respect(s) du repos quotidien",
            description="Règlementation expirée",
            date_application_start=datetime(2018, 1, 1),
            date_application_end=datetime(2019, 11, 1),
            regulation_rule="dailyRest",
            variables=None,
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

            db.session.add(
                MissionEnd(
                    submitter=employee,
                    reception_time=get_time(how_many_days_ago, hour=19),
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
        ## GIVEN
        employee = self.employee
        period_start = get_date(how_many_days_ago=18)
        period_end = get_date(how_many_days_ago=3)

        ## WHEN
        regulations.compute_regulations(
            employee, period_start, period_end, SubmitterType.EMPLOYEE
        )

        ## THEN
        self.assertEqual(mock_compute_regulations_per_day.call_count, 16)
