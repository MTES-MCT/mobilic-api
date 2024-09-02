from datetime import datetime, timedelta
from unittest.mock import patch

from app import db
from app.domain import regulations
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.helpers.submitter_type import SubmitterType
from app.models import (
    RegulationComputation,
    User,
    RegulationCheck,
    RegulatoryAlert,
    Mission,
)
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType, UnitType
from app.seed.helpers import (
    get_time,
    get_date,
    AuthenticatedUserContext,
    get_datetime_tz,
)
from app.services.get_regulation_checks import RegulationCheckData
from app.tests.helpers import insert_regulation_check
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestRegulationsCommon(RegulationsTest):
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

    def test_no_computation_for_empty_previous_day(self):
        start_time = get_datetime_tz(2024, 8, 21, 10, 0)
        end_time = get_datetime_tz(2024, 8, 21, 15, 0)
        self._log_and_validate_mission(
            mission_name="5h work",
            submitter=self.employee,
            work_periods=[
                [
                    start_time,
                    end_time,
                ],
            ],
        )
        day_start = start_time.date()
        day_before = start_time.date() - timedelta(days=1)
        computation_done = RegulationComputation.query.filter(
            RegulationComputation.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationComputation.day == day_start,
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(computation_done)
        computation_done = RegulationComputation.query.filter(
            RegulationComputation.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationComputation.day == day_before,
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNone(computation_done)

    def test_computation_for_non_empty_day(self):
        self.employee
        how_many_days_ago = 2

        self._log_and_validate_mission(
            mission_name="long night",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago + 1, hour=20),
                    get_time(how_many_days_ago=how_many_days_ago, hour=5),
                ],
            ],
        )

        day_start = get_date(how_many_days_ago)
        day_before = get_date(how_many_days_ago + 1)
        computation_done = RegulationComputation.query.filter(
            RegulationComputation.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationComputation.day == day_start,
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(computation_done)
        computation_done = RegulationComputation.query.filter(
            RegulationComputation.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationComputation.day == day_before,
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(computation_done)

    def test_use_latest_regulation_check_by_type(self):
        company = self.company
        employee = self.employee
        how_many_days_ago = 2

        expired_regulation_data = RegulationCheckData(
            id=6,
            type="minimumDailyRest",
            label="Non-respect(s) du repos quotidien",
            date_application_start=get_datetime_tz(2018, 1, 1),
            date_application_end=get_datetime_tz(2019, 11, 1),
            regulation_rule="dailyRest",
            variables=None,
            unit=UnitType.DAY,
        )
        insert_regulation_check(
            session=db.session, regulation_check_data=expired_regulation_data
        )

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

        self._log_and_validate_mission(
            mission_name="super long mission",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2024, 7, 25, 4, 0),
                    get_datetime_tz(2024, 8, 9, 5, 0),
                ],
            ],
        )

        # THEN
        self.assertEqual(mock_compute_regulations_per_day.call_count, 17)

        computations_done = RegulationComputation.query.filter(
            RegulationComputation.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(len(computations_done), 17)
