from datetime import datetime, date

from app import db
from app.domain.log_activities import log_activity
from app.domain.regulations_per_week import NATINF_13152
from app.domain.validation import validate_mission
from app.helpers.submitter_type import SubmitterType
from app.models import (
    RegulatoryAlert,
    User,
    RegulationCheck,
    Mission,
    RegulationComputation,
)
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.seed.helpers import (
    get_time,
    AuthenticatedUserContext,
    get_datetime_tz,
)
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestWeeklyRules(RegulationsTest):
    def test_compute_regulations_per_week_success(self):
        nb_weeks = 3
        for i in range(nb_weeks):
            how_many_days_ago = 3 + i * 7
            self._log_and_validate_mission(
                mission_name=f"mission #{i}",
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

                if i == 8:
                    log_activity(
                        submitter=employee,
                        user=employee,
                        mission=missions[i],
                        type=ActivityType.DRIVE,
                        switch_mode=False,
                        reception_time=get_datetime_tz(2022, 7, 6 + i, 17),
                        start_time=get_datetime_tz(2022, 7, 6 + i, 3),
                        end_time=get_datetime_tz(2022, 7, 6 + i, 4),
                    )

                    validate_mission(
                        submitter=employee,
                        mission=missions[i],
                        for_user=employee,
                    )
                else:
                    log_activity(
                        submitter=employee,
                        user=employee,
                        mission=missions[i],
                        type=ActivityType.DRIVE,
                        switch_mode=False,
                        reception_time=get_datetime_tz(2022, 7, 6 + i, 21),
                        start_time=get_datetime_tz(2022, 7, 6 + i, 20),
                        end_time=get_datetime_tz(2022, 7, 6 + i, 21),
                    )

                    validate_mission(
                        submitter=employee,
                        mission=missions[i],
                        for_user=employee,
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
        extra_info = regulatory_alert.extra
        self.assertEqual(extra_info["max_nb_days_worked_by_week"], 6)
        self.assertEqual(extra_info["min_weekly_break_in_hours"], 34)
        self.assertTrue(extra_info["too_many_days"])
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
        extra_info = regulatory_alert.extra
        self.assertFalse(extra_info["too_many_days"])
        self.assertEqual(extra_info["rest_duration_s"], 111600)
        self.assertEqual(extra_info["sanction_code"], NATINF_13152)

    def test_weekly_rule_should_mark_beginning_of_week_as_computed(self):

        self._log_and_validate_mission(
            mission_name="Work on end of weeks",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2024, 8, 2, 8, 0),
                    get_datetime_tz(2024, 8, 2, 18, 0),
                ],
                [
                    get_datetime_tz(2024, 8, 9, 8, 0),
                    get_datetime_tz(2024, 8, 9, 18, 0),
                ],
            ],
        )

        # Should have regulation computations on mondays
        res = RegulationComputation.query.filter(
            RegulationComputation.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationComputation.day == date(2024, 8, 5),
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(res)

        res = RegulationComputation.query.filter(
            RegulationComputation.user.has(User.email == EMPLOYEE_EMAIL),
            RegulationComputation.day == date(2024, 7, 29),
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).one_or_none()
        self.assertIsNotNone(res)
