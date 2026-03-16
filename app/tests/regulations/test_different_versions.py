from datetime import datetime

from app import db
from app.domain.log_activities import log_activity
from app.helpers.submitter_type import SubmitterType
from app.models import RegulatoryAlert, User, RegulationCheck, Mission
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.seed import AuthenticatedUserContext
from app.seed.helpers import get_time, get_date
from app.tests import test_post_graphql
from app.tests.helpers import ApiRequests
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestDifferentVersions(RegulationsTest):
    def test_employee_validation_after_admin_edit_no_crash(self):
        """Validating a mission as employee should not crash when a previously
        validated mission in the same period was edited by an admin.

        Setup:
          1. Employee validates mission1 with activity A (8h-15h)
          2. Admin shortens A to 8h-12h and adds activity B (13h-15h)
             DB is valid: A(8-12) + B(13-15), no overlap
             But employee version of A is still (8-15), which overlaps B

        Trigger:
          3. Employee validates mission2 on the same day via GraphQL
             compute_regulations loads mission1, freezes A back to (8-15)
             SET CONSTRAINTS IMMEDIATE + autoflush → ExclusionViolation
        """
        how_many_days_ago = 3

        mission1 = self._log_and_validate_mission(
            mission_name="first mission",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=8),
                    get_time(how_many_days_ago=how_many_days_ago, hour=15),
                ],
            ],
        )

        activity = mission1.activities_for(user=self.employee)[0]
        test_post_graphql(
            query=ApiRequests.validate_mission,
            mock_authentication_with_user=self.admin,
            variables={
                "missionId": mission1.id,
                "usersIds": [self.employee.id],
                "activityItems": [
                    {
                        "edit": {
                            "activityId": activity.id,
                            "endTime": int(
                                get_time(
                                    how_many_days_ago=how_many_days_ago,
                                    hour=12,
                                ).timestamp()
                            ),
                        }
                    },
                    {
                        "log": {
                            "type": "support",
                            "missionId": mission1.id,
                            "userId": self.employee.id,
                            "startTime": int(
                                get_time(
                                    how_many_days_ago=how_many_days_ago,
                                    hour=13,
                                ).timestamp()
                            ),
                            "endTime": int(
                                get_time(
                                    how_many_days_ago=how_many_days_ago,
                                    hour=15,
                                ).timestamp()
                            ),
                            "switch": False,
                        }
                    },
                ],
            },
        )

        mission2 = Mission(
            name="second mission",
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.employee,
        )
        db.session.add(mission2)
        db.session.commit()

        with AuthenticatedUserContext(user=self.employee):
            log_activity(
                submitter=self.employee,
                user=self.employee,
                mission=mission2,
                type=ActivityType.DRIVE,
                switch_mode=False,
                reception_time=get_time(how_many_days_ago, hour=20),
                start_time=get_time(how_many_days_ago, hour=16),
                end_time=get_time(how_many_days_ago, hour=20),
            )

        res = test_post_graphql(
            query=ApiRequests.validate_mission,
            mock_authentication_with_user=self.employee,
            variables={
                "missionId": mission2.id,
                "usersIds": [self.employee.id],
            },
        )
        self.assertIsNone(res.json.get("errors"))

    def test_employee_max_work_day_alert_preserved_after_admin_edit(self):
        """Admin reduces work hours below 12h threshold, but employee version
        should still show the MAXIMUM_WORK_DAY_TIME alert based on original hours.
        """
        how_many_days_ago = 3
        day_start = get_date(how_many_days_ago)

        mission = self._log_and_validate_mission(
            mission_name="13h work day",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=8),
                    get_time(how_many_days_ago=how_many_days_ago, hour=21),
                ],
            ],
        )

        employee_alerts_before = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(len(employee_alerts_before), 1)

        activity = mission.activities_for(user=self.employee)[0]
        test_post_graphql(
            query=ApiRequests.validate_mission,
            mock_authentication_with_user=self.admin,
            variables={
                "missionId": mission.id,
                "usersIds": [self.employee.id],
                "activityItems": [
                    {
                        "edit": {
                            "activityId": activity.id,
                            "endTime": int(
                                get_time(
                                    how_many_days_ago=how_many_days_ago,
                                    hour=19,
                                ).timestamp()
                            ),
                        }
                    }
                ],
            },
        )

        employee_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(len(employee_alerts), 1)

        admin_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.ADMIN,
        ).all()
        self.assertEqual(len(admin_alerts), 0)

        res = test_post_graphql(
            query=ApiRequests.regulation_computations_by_day,
            mock_authentication_with_user=self.employee,
            variables={
                "userId": self.employee.id,
                "fromDate": day_start.strftime("%Y-%m-%d"),
                "endDate": day_start.strftime("%Y-%m-%d"),
            },
        )
        result_computations = res.json["data"]["user"][
            "regulationComputationsByDay"
        ][0]["regulationComputations"]

        for rc in result_computations:
            alert = [
                check
                for check in rc["regulationChecks"]
                if check["type"] == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ][0]["alert"]
            if rc["submitterType"] == SubmitterType.ADMIN:
                self.assertIsNone(alert)
            else:
                self.assertIsNotNone(alert)

    def test_admin_adds_hours_creates_admin_alert_not_employee(self):
        """Admin increases work hours above 12h threshold, but employee version
        should NOT show the MAXIMUM_WORK_DAY_TIME alert since original hours were below.
        """
        how_many_days_ago = 3
        day_start = get_date(how_many_days_ago)

        mission = self._log_and_validate_mission(
            mission_name="11h work day",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=8),
                    get_time(how_many_days_ago=how_many_days_ago, hour=19),
                ],
            ],
        )

        employee_alerts_before = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(len(employee_alerts_before), 0)

        activity = mission.activities_for(user=self.employee)[0]
        test_post_graphql(
            query=ApiRequests.validate_mission,
            mock_authentication_with_user=self.admin,
            variables={
                "missionId": mission.id,
                "usersIds": [self.employee.id],
                "activityItems": [
                    {
                        "edit": {
                            "activityId": activity.id,
                            "endTime": int(
                                get_time(
                                    how_many_days_ago=how_many_days_ago,
                                    hour=22,
                                ).timestamp()
                            ),
                        }
                    }
                ],
            },
        )

        employee_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(len(employee_alerts), 0)

        admin_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type
                == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.ADMIN,
        ).all()
        self.assertEqual(len(admin_alerts), 1)

        res = test_post_graphql(
            query=ApiRequests.regulation_computations_by_day,
            mock_authentication_with_user=self.employee,
            variables={
                "userId": self.employee.id,
                "fromDate": day_start.strftime("%Y-%m-%d"),
                "endDate": day_start.strftime("%Y-%m-%d"),
            },
        )
        result_computations = res.json["data"]["user"][
            "regulationComputationsByDay"
        ][0]["regulationComputations"]

        for rc in result_computations:
            alert = [
                check
                for check in rc["regulationChecks"]
                if check["type"] == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
            ][0]["alert"]
            if rc["submitterType"] == SubmitterType.ADMIN:
                self.assertIsNotNone(alert)
            else:
                self.assertIsNone(alert)

    def test_employee_alert_admin_no_alert_regulations_query(self):
        how_many_days_ago = 3
        day_start = get_date(how_many_days_ago)

        # Employee logs a mission with insufficient break
        mission = self._log_and_validate_mission(
            mission_name="6h30 work with 15m break",
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=8),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=30
                    ),
                ],
                [
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=11, minute=45
                    ),
                    get_time(
                        how_many_days_ago=how_many_days_ago, hour=14, minute=45
                    ),
                ],
            ],
        )

        # Admin cancels first activity (break time is now ok)
        test_post_graphql(
            query=ApiRequests.validate_mission,
            mock_authentication_with_user=self.admin,
            variables={
                "missionId": mission.id,
                "usersIds": [self.employee.id],
                "activityItems": [
                    {
                        "cancel": {
                            "activityId": mission.activities_for(
                                user=self.employee
                            )[0].id
                        }
                    }
                ],
            },
        )

        employee_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.ENOUGH_BREAK
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        self.assertEqual(len(employee_alerts), 1)

        admin_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user.has(User.email == EMPLOYEE_EMAIL),
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == RegulationCheckType.ENOUGH_BREAK
            ),
            RegulatoryAlert.day == day_start,
            RegulatoryAlert.submitter_type == SubmitterType.ADMIN,
        ).all()
        self.assertEqual(len(admin_alerts), 0)

        res = test_post_graphql(
            query=ApiRequests.regulation_computations_by_day,
            mock_authentication_with_user=self.employee,
            variables={
                "userId": self.employee.id,
                "fromDate": day_start.strftime("%Y-%m-%d"),
                "endDate": day_start.strftime("%Y-%m-%d"),
            },
        )
        result_computations = res.json["data"]["user"][
            "regulationComputationsByDay"
        ][0]["regulationComputations"]

        # Admin version should have no alert
        # Employee version should have an alert
        for rc in result_computations:
            alert = [
                check
                for check in rc["regulationChecks"]
                if check["type"] == RegulationCheckType.ENOUGH_BREAK
            ][0]["alert"]
            if rc["submitterType"] == SubmitterType.ADMIN:
                self.assertIsNone(alert)
            else:
                self.assertIsNotNone(alert)
