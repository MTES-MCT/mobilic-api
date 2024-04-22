from datetime import datetime

from app.helpers.submitter_type import SubmitterType
from app.models import RegulationComputation
from app.seed.helpers import get_time
from app.tests.helpers import make_authenticated_request, ApiRequests
from app.tests.regulations import RegulationsTest


class TestDifferentPeriods(RegulationsTest):
    def test_regulation_computations_applied_on_initial_time_range(self):
        how_many_days_ago = 3

        # Employee logs a mission over three days
        mission = self._log_and_validate_mission(
            mission_name="Mission over three days",
            company=self.company,
            reception_time=datetime.now(),
            submitter=self.employee,
            work_periods=[
                [
                    get_time(how_many_days_ago=how_many_days_ago + 1, hour=21),
                    get_time(how_many_days_ago=how_many_days_ago, hour=3),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago, hour=18),
                    get_time(how_many_days_ago=how_many_days_ago, hour=23),
                ],
                [
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=2),
                    get_time(how_many_days_ago=how_many_days_ago - 1, hour=5),
                ],
            ],
        )

        employee_computations = RegulationComputation.query.filter(
            RegulationComputation.user_id == self.employee.id,
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).all()

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

        admin_computations = RegulationComputation.query.filter(
            RegulationComputation.user_id == self.employee.id,
            RegulationComputation.submitter_type == SubmitterType.ADMIN,
        ).all()

        # There should be the same number of regulation computations of type Employee and Admin
        self.assertEqual(3, len(employee_computations))
        self.assertEqual(len(employee_computations), len(admin_computations))
