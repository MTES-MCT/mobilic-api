from datetime import datetime, timedelta

from flask.ctx import AppContext

from app import app
from app.domain.validation import validate_mission
from app.jobs.auto_validations import (
    EMPLOYEE_THRESHOLD_HOURS,
    get_auto_validations,
    job_process_auto_validations,
)
from app.models import MissionAutoValidation, Mission, MissionValidation
from app.seed import CompanyFactory, UserFactory
from app.seed.helpers import get_time, AuthenticatedUserContext
from app.tests import BaseTest
from app.tests.helpers import _log_activities_in_mission, WorkPeriod


class TestAutoValidation(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.team_leader = UserFactory.create(
            first_name="Tim",
            last_name="Leader",
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.team_mates = [
            UserFactory.create(
                post__company=self.company, first_name="Tim", last_name="Mate"
            )
            for i in range(0, 3)
        ]

        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_employee_logs_for_himself(self):

        ## An employee logs two activities for himself in a mission

        employee = self.team_mates[0]
        first_time = datetime.now()
        mission_id = _log_activities_in_mission(
            submitter=employee,
            company=self.company,
            user=employee,
            work_periods=[
                WorkPeriod(
                    start_time=get_time(2, 8), end_time=get_time(2, 10)
                ),
            ],
            submission_time=first_time,
        )
        _log_activities_in_mission(
            submitter=employee,
            company=self.company,
            user=employee,
            work_periods=[
                WorkPeriod(
                    start_time=get_time(2, 14), end_time=get_time(2, 16)
                ),
            ],
            mission_id=mission_id,
        )

        ## There should be one auto validation at time of first reception
        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(1, len(auto_validations))
        auto_validation = auto_validations[0]
        self.assertEqual(auto_validation.user_id, employee.id)
        self.assertEqual(auto_validation.reception_time, first_time)
        self.assertEqual(auto_validation.mission_id, mission_id)
        self.assertFalse(auto_validation.is_admin)

    def test_employee_logs_for_team(self):

        ## An employee logs two activities for himself and then for a teammate in a mission

        logger = self.team_mates[0]
        team_mate_1 = self.team_mates[1]

        first_time = datetime.now()
        mission_id = _log_activities_in_mission(
            submitter=logger,
            company=self.company,
            user=logger,
            work_periods=[
                WorkPeriod(
                    start_time=get_time(2, 8), end_time=get_time(2, 10)
                ),
            ],
            submission_time=first_time,
        )
        second_time = datetime.now()
        _log_activities_in_mission(
            submitter=logger,
            company=self.company,
            user=team_mate_1,
            work_periods=[
                WorkPeriod(
                    start_time=get_time(2, 14), end_time=get_time(2, 16)
                ),
            ],
            mission_id=mission_id,
            submission_time=second_time,
        )

        ## There should be one auto validation at time of first reception for himself
        auto_validations_himself = MissionAutoValidation.query.filter(
            MissionAutoValidation.user == logger
        ).all()
        self.assertEqual(1, len(auto_validations_himself))
        auto_validation = auto_validations_himself[0]
        self.assertEqual(auto_validation.user_id, logger.id)
        self.assertEqual(auto_validation.reception_time, first_time)

        ## There should be one auto validation at time of second reception for teammate
        auto_validations_teammate = MissionAutoValidation.query.filter(
            MissionAutoValidation.user == team_mate_1
        ).all()
        self.assertEqual(1, len(auto_validations_teammate))
        auto_validation = auto_validations_teammate[0]
        self.assertEqual(auto_validation.user_id, team_mate_1.id)
        self.assertEqual(auto_validation.reception_time, second_time)

    def test_do_not_create_auto_validation_for_admin(self):

        _log_activities_in_mission(
            submitter=self.team_leader,
            company=self.company,
            user=self.team_leader,
            work_periods=[
                WorkPeriod(
                    start_time=get_time(2, 8), end_time=get_time(2, 10)
                ),
            ],
        )

        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(0, len(auto_validations))

    def test_validating_mission_removes_auto_validation(self):
        ## An employee logs an activity for himself in a mission
        employee = self.team_mates[0]
        mission_id = _log_activities_in_mission(
            submitter=employee,
            company=self.company,
            user=employee,
            work_periods=[
                WorkPeriod(
                    start_time=get_time(2, 8), end_time=get_time(2, 10)
                ),
            ],
        )
        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(1, len(auto_validations))

        mission = Mission.query.get(mission_id)
        with AuthenticatedUserContext(user=employee):
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(0, len(auto_validations))

    def test_auto_validation_mission_recorded_one_day_ago(self):
        ## An employee logs an activity for himself more than a day ago

        now = datetime.now()
        more_than_a_day_ago = now - timedelta(
            hours=EMPLOYEE_THRESHOLD_HOURS + 1
        )

        employee = self.team_mates[0]
        mission_id = _log_activities_in_mission(
            submitter=employee,
            company=self.company,
            user=employee,
            work_periods=[
                WorkPeriod(
                    start_time=get_time(2, 8), end_time=get_time(2, 10)
                ),
            ],
            submission_time=more_than_a_day_ago,
        )

        # An employee auto validation should exist
        auto_validations = get_auto_validations(now=now)
        self.assertEqual(1, len(auto_validations))

        # Cron job runs
        job_process_auto_validations()

        # An admin auto validation should exist
        auto_validations = get_auto_validations(now=now)
        self.assertEqual(1, len(auto_validations))
        self.assertTrue(auto_validations[0].is_admin)

        # Mission should be validated
        validations = MissionValidation.query.all()
        self.assertEqual(1, len(validations))
        validation = validations[0]
        self.assertEqual(validation.mission_id, mission_id)
        self.assertEqual(validation.is_admin, False)
        self.assertEqual(validation.is_auto, True)
        self.assertIsNone(validation.submitter_id)

        with self.assertRaises(Exception):
            # Employee shouldn't be able to validate this mission
            mission = Mission.query.get(mission_id)
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

    def test_auto_validation_mission_recorded_less_one_day_ago(self):
        ## An employee logs an activity for himself less than a day ago

        now = datetime.now()
        less_than_a_day_ago = now - timedelta(
            hours=EMPLOYEE_THRESHOLD_HOURS - 1
        )

        employee = self.team_mates[0]
        _log_activities_in_mission(
            submitter=employee,
            company=self.company,
            user=employee,
            work_periods=[
                WorkPeriod(
                    start_time=get_time(2, 8), end_time=get_time(2, 10)
                ),
            ],
            submission_time=less_than_a_day_ago,
        )
        auto_validations = get_auto_validations(now=now)
        self.assertEqual(0, len(auto_validations))
