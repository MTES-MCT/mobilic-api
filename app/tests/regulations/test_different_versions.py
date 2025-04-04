from datetime import datetime

from app.helpers.submitter_type import SubmitterType
from app.models import RegulatoryAlert, User, RegulationCheck
from app.models.regulation_check import RegulationCheckType
from app.seed.helpers import get_time, get_date
from app.tests import test_post_graphql
from app.tests.helpers import ApiRequests
from app.tests.regulations import RegulationsTest, EMPLOYEE_EMAIL


class TestDifferentVersions(RegulationsTest):
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
