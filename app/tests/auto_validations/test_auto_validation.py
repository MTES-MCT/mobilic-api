from datetime import datetime, timedelta

from flask.ctx import AppContext
from freezegun import freeze_time

from app import app
from app.domain.validation import validate_mission
from app.helpers.errors import (
    MissingJustificationForAdminValidation,
    MissionAlreadyAutoValidatedError,
)
from app.helpers.time import to_timestamp, LOCAL_TIMEZONE
from app.jobs.auto_validations import (
    get_employee_auto_validations,
    job_process_auto_validations,
)
from app.models import MissionAutoValidation, Mission, MissionValidation
from app.models.mission_validation import OverValidationJustification
from app.seed import CompanyFactory, UserFactory
from app.seed.helpers import get_time, AuthenticatedUserContext
from app.tests import BaseTest
from app.tests.helpers import (
    _log_activities_in_mission,
    WorkPeriod,
    init_regulation_checks_data,
    init_businesses_data,
    make_authenticated_request,
    ApiRequests,
)


class TestAutoValidation(BaseTest):
    def setUp(self):
        super().setUp()

        init_regulation_checks_data()
        init_businesses_data()

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

    def _create_mission_and_auto_validate_for_third_party_tests(
        self, employee=None
    ):
        """Helper method specifically for third-party tests with fixed dates"""
        if employee is None:
            employee = self.team_mates[0]

        with freeze_time(datetime(2025, 1, 15, 18, 0)):
            mission_id = _log_activities_in_mission(
                submitter=employee,
                company=self.company,
                user=employee,
                work_periods=[
                    WorkPeriod(
                        start_time=get_time(0, 8), end_time=get_time(0, 10)
                    ),
                ],
            )

        with freeze_time(datetime(2025, 1, 16, 19, 0)):
            job_process_auto_validations()

        mission = Mission.query.get(mission_id)
        return mission_id, mission

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

    def test_auto_validation_for_admin(self):

        mission_id = _log_activities_in_mission(
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
        self.assertEqual(1, len(auto_validations))
        auto_validation = auto_validations[0]
        self.assertEqual(auto_validation.user_id, self.team_leader.id)
        self.assertEqual(auto_validation.mission_id, mission_id)
        self.assertTrue(auto_validation.is_admin)

    def test_validating_employee_mission_removes_auto_validation_creates_admin_auto_validation(
        self,
    ):

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
        self.assertFalse(auto_validations[0].is_admin)

        mission = Mission.query.get(mission_id)
        with AuthenticatedUserContext(user=employee):
            validate_mission(
                submitter=employee, mission=mission, for_user=employee
            )

        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(1, len(auto_validations))
        self.assertTrue(auto_validations[0].is_admin)

    def test_auto_validation_mission_recorded_one_day_ago(self):
        ## An employee logs an activity for himself more than a day ago

        now = datetime(2025, 5, 7, 18, 0)
        with freeze_time(now):
            more_than_a_day_ago = get_time(1, 17)

            employee = self.team_mates[0]
            mission_id = _log_activities_in_mission(
                submitter=employee,
                company=self.company,
                user=employee,
                work_periods=[
                    WorkPeriod(
                        start_time=get_time(1, 8), end_time=get_time(1, 10)
                    ),
                ],
                submission_time=more_than_a_day_ago,
            )

            # An employee auto validation should exist
            auto_validations = get_employee_auto_validations(now=now)
            self.assertEqual(1, len(auto_validations))

            # Cron job runs
            job_process_auto_validations()

            # An admin auto validation should exist
            auto_validations = MissionAutoValidation.query.all()
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

    def test_get_auto_validations_when_mission_recorded_less_one_day_ago(self):
        ## An employee logs an activity for himself less than a day ago

        with freeze_time(datetime(2025, 5, 7, 18, 0)):
            now = datetime.now()
            less_than_a_day_ago = get_time(1, 19, tz=LOCAL_TIMEZONE)

            employee = self.team_mates[0]
            _log_activities_in_mission(
                submitter=employee,
                company=self.company,
                user=employee,
                work_periods=[
                    WorkPeriod(
                        start_time=get_time(1, 8), end_time=get_time(1, 10)
                    ),
                ],
                submission_time=less_than_a_day_ago,
            )
            auto_validations = get_employee_auto_validations(now=now)
            self.assertEqual(0, len(auto_validations))

    def test_mission_gets_auto_validated_employee_and_admin(self):

        # employee logs time on a thursday
        employee = self.team_mates[0]
        with freeze_time(datetime(2025, 4, 17, 18, 0)):
            _log_activities_in_mission(
                submitter=employee,
                company=self.company,
                user=employee,
                work_periods=[
                    WorkPeriod(
                        start_time=get_time(0, 8), end_time=get_time(0, 10)
                    ),
                ],
            )

        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(1, len(auto_validations))
        auto_validation = auto_validations[0]
        self.assertFalse(auto_validation.is_admin)

        # it gets validated on friday - and it creates an admin auto validation
        with freeze_time(datetime(2025, 4, 18, 19, 0)):
            job_process_auto_validations()

        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(1, len(auto_validations))
        auto_validation = auto_validations[0]
        self.assertTrue(auto_validation.is_admin)

        # which does not get validated 2 days after because it's a sunday
        with freeze_time(datetime(2025, 4, 20, 20, 0)):
            job_process_auto_validations()

        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(1, len(auto_validations))

        # 19 and 20 are weekends, 21 is a bank holiday so it will gets validated on 23rd after 19h00
        with freeze_time(datetime(2025, 4, 23, 18, 0)):
            job_process_auto_validations()

        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(1, len(auto_validations))

        with freeze_time(datetime(2025, 4, 23, 20, 0)):
            job_process_auto_validations()

        auto_validations = MissionAutoValidation.query.all()
        self.assertEqual(0, len(auto_validations))

        mission_validations = MissionValidation.query.all()
        self.assertEqual(2, len(mission_validations))

    def test_admin_cannot_validate_after_admin_auto_validation_without_justification(
        self,
    ):
        # employee logs time on a monday
        employee = self.team_mates[0]
        with freeze_time(datetime(2025, 5, 12, 18, 0)):
            initial_start_time = get_time(0, 8)
            mission_id = _log_activities_in_mission(
                submitter=employee,
                company=self.company,
                user=employee,
                work_periods=[
                    WorkPeriod(
                        start_time=initial_start_time, end_time=get_time(0, 10)
                    ),
                ],
            )

        # auto validation employee on tuesday
        with freeze_time(datetime(2025, 5, 13, 19, 0)):
            job_process_auto_validations()

        # auto validation admin on thursday
        with freeze_time(datetime(2025, 5, 15, 19, 30)):
            job_process_auto_validations()

        validations = MissionValidation.query.all()
        self.assertEqual(2, len(validations))

        # admin can not update/validate mission
        mission = Mission.query.get(mission_id)
        res = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.team_leader.id,
            query=ApiRequests.validate_mission,
            variables=dict(
                mission_id=mission_id,
                users_ids=[employee.id],
                activity_items=[
                    {
                        "edit": {
                            "activityId": mission.activities[0].id,
                            "startTime": to_timestamp(
                                initial_start_time + timedelta(minutes=30)
                            ),
                        }
                    },
                ],
            ),
        )
        error = res["errors"][0]
        self.assertEqual(
            error["extensions"]["code"],
            MissingJustificationForAdminValidation.code,
        )

        # admin can update/validate with a justification
        res = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.team_leader.id,
            query=ApiRequests.validate_mission,
            variables=dict(
                mission_id=mission_id,
                users_ids=[employee.id],
                justification=OverValidationJustification.PROFESSIONAL,
                activity_items=[
                    {
                        "edit": {
                            "activityId": mission.activities[0].id,
                            "startTime": to_timestamp(
                                initial_start_time + timedelta(minutes=30)
                            ),
                        }
                    },
                ],
            ),
        )
        self.assertFalse("errors" in res)

    def test_employee_cannot_validate_after_employee_auto_validation(self):
        employee = self.team_mates[0]
        (
            mission_id,
            mission,
        ) = self._create_mission_and_auto_validate_for_third_party_tests(
            employee
        )

        validations = MissionValidation.query.filter(
            MissionValidation.mission_id == mission_id,
            MissionValidation.user_id == employee.id,
            MissionValidation.is_auto == True,
            MissionValidation.is_admin == False,
        ).all()
        self.assertEqual(1, len(validations))

        with AuthenticatedUserContext(user=employee):
            with self.assertRaises(
                MissionAlreadyAutoValidatedError
            ) as context:
                validate_mission(
                    submitter=employee, mission=mission, for_user=employee
                )

        self.assertEqual(
            str(context.exception),
            "This mission has already been automatically validated",
        )
        self.assertEqual(
            context.exception.code,
            "MISSION_ALREADY_AUTO_VALIDATED",
        )

    def test_employee_cannot_validate_after_admin_auto_validation(self):
        employee = self.team_mates[0]

        with freeze_time(datetime(2025, 4, 17, 18, 0)):
            mission_id = _log_activities_in_mission(
                submitter=employee,
                company=self.company,
                user=employee,
                work_periods=[
                    WorkPeriod(
                        start_time=get_time(0, 8), end_time=get_time(0, 10)
                    ),
                ],
            )

        with freeze_time(datetime(2025, 4, 18, 19, 0)):
            job_process_auto_validations()

        with freeze_time(datetime(2025, 4, 23, 20, 0)):
            job_process_auto_validations()

        validations = MissionValidation.query.filter(
            MissionValidation.mission_id == mission_id,
            MissionValidation.user_id == employee.id,
            MissionValidation.is_auto == True,
            MissionValidation.is_admin == True,
        ).all()
        self.assertEqual(1, len(validations))

        mission = Mission.query.get(mission_id)

        with self.assertRaises(MissionAlreadyAutoValidatedError) as context:
            validate_mission(
                submitter=employee,
                mission=mission,
                for_user=employee,
                is_admin_validation=False,
            )

        self.assertEqual(
            str(context.exception),
            "This mission has already been automatically validated",
        )
        self.assertEqual(
            context.exception.code,
            "MISSION_ALREADY_AUTO_VALIDATED",
        )

    def test_employee_can_validate_before_auto_validation(self):
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

        auto_validations = MissionAutoValidation.query.filter(
            MissionAutoValidation.mission_id == mission_id
        ).all()
        self.assertEqual(1, len(auto_validations))

        processed_validations = MissionValidation.query.filter(
            MissionValidation.mission_id == mission_id,
            MissionValidation.is_auto == True,
        ).all()
        self.assertEqual(0, len(processed_validations))

        mission = Mission.query.get(mission_id)

        validation = validate_mission(
            submitter=employee,
            mission=mission,
            for_user=employee,
            is_admin_validation=False,
        )
        self.assertIsNotNone(validation)
        self.assertFalse(validation.is_auto)

    def test_employee_cannot_edit_mission_after_auto_validation(self):
        employee = self.team_mates[0]
        (
            _,
            mission,
        ) = self._create_mission_and_auto_validate_for_third_party_tests(
            employee
        )

        with AuthenticatedUserContext(user=employee):
            with self.assertRaises(MissionAlreadyAutoValidatedError):
                from app.domain.permissions import (
                    check_actor_can_write_on_mission_over_period,
                )

                check_actor_can_write_on_mission_over_period(
                    actor=employee, mission=mission, for_user=employee
                )

    def test_employee_cannot_edit_activity_after_auto_validation(self):
        employee = self.team_mates[0]
        (
            _,
            mission,
        ) = self._create_mission_and_auto_validate_for_third_party_tests(
            employee
        )
        activity = mission.activities[0]

        from app.domain.permissions import (
            check_actor_can_write_on_mission_over_period,
        )

        with AuthenticatedUserContext(user=employee):
            with self.assertRaises(MissionAlreadyAutoValidatedError):
                check_actor_can_write_on_mission_over_period(
                    actor=employee,
                    mission=mission,
                    for_user=employee,
                    start=activity.start_time,
                    end=activity.end_time,
                )

    def test_employee_cannot_add_activity_after_auto_validation(self):
        employee = self.team_mates[0]
        (
            _,
            mission,
        ) = self._create_mission_and_auto_validate_for_third_party_tests(
            employee
        )

        from app.domain.permissions import (
            check_actor_can_write_on_mission_over_period,
        )

        with AuthenticatedUserContext(user=employee):
            with self.assertRaises(MissionAlreadyAutoValidatedError):
                check_actor_can_write_on_mission_over_period(
                    actor=employee,
                    mission=mission,
                    for_user=employee,
                    start=get_time(0, 14),
                    end=get_time(0, 16),
                )
