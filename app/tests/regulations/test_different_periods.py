from datetime import datetime
from app.helpers.submitter_type import SubmitterType
from app.models import RegulationComputation
from app.seed.helpers import get_datetime_tz
from app.tests.helpers import ApiRequests, make_authenticated_request
from app.tests.regulations import RegulationsTest


class TestDifferentPeriods(RegulationsTest):
    def test_regulation_computations_applied_on_initial_time_range(self):
        employee_id = self.employee.id

        # Employee logs a mission over three days
        mission = self._log_and_validate_mission(
            mission_name="Mission over three days",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2024, 8, 14, 21, 0),
                    get_datetime_tz(2024, 8, 15, 3, 0),
                ],
                [
                    get_datetime_tz(2024, 8, 15, 18, 0),
                    get_datetime_tz(2024, 8, 15, 23, 0),
                ],
                [
                    get_datetime_tz(2024, 8, 16, 2, 0),
                    get_datetime_tz(2024, 8, 16, 5, 0),
                ],
            ],
        )

        # Admin cancel first and last activities and validates
        # Mission is now on only one day from the admin perspective
        make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.validate_mission,
            variables=dict(
                mission_id=mission.id,
                users_ids=[self.employee.id],
                activity_items=[
                    {"cancel": {"activityId": mission.activities[0].id}},
                    {"cancel": {"activityId": mission.activities[-1].id}},
                ],
            ),
        )

        employee_computations = RegulationComputation.query.filter(
            RegulationComputation.user_id == employee_id,
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).all()

        # 3 days + 1 week computed
        self.assertEqual(4, len(employee_computations))

        admin_computations = RegulationComputation.query.filter(
            RegulationComputation.user_id == employee_id,
            RegulationComputation.submitter_type == SubmitterType.ADMIN,
        ).all()

        # There should be the same number of regulation computations of type Employee and Admin
        self.assertEqual(len(employee_computations), len(admin_computations))
