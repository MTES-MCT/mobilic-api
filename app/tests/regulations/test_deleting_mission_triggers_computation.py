from datetime import datetime

from app.helpers.submitter_type import SubmitterType
from app.models import RegulationComputation
from app.seed.helpers import get_datetime_tz
from app.tests.helpers import make_authenticated_request, ApiRequests
from app.tests.regulations import RegulationsTest


class TestDeletingMissionTriggersComputation(RegulationsTest):
    def _get_computations_nb_for_date(self, date):
        employee_computations = RegulationComputation.query.filter(
            RegulationComputation.user == self.employee,
            RegulationComputation.day == date,
            RegulationComputation.submitter_type == SubmitterType.EMPLOYEE,
        ).all()
        admin_computations = RegulationComputation.query.filter(
            RegulationComputation.user == self.employee,
            RegulationComputation.day == date,
            RegulationComputation.submitter_type == SubmitterType.ADMIN,
        ).all()
        return len(employee_computations), len(admin_computations)

    def test_admin_deletes_mission_triggers_computations(self):
        # Employee logs a mission with too many work hours
        long_mission = self._log_and_validate_mission(
            mission_name="Long mission",
            submitter=self.employee,
            work_periods=[
                [
                    get_datetime_tz(2024, 10, 7, 3, 0),  # lundi
                    get_datetime_tz(2024, 10, 7, 22, 0),
                ],
            ],
        )

        (
            nb_employee_computations,
            nb_admin_computations,
        ) = self._get_computations_nb_for_date("2024-10-7")
        self.assertEqual(nb_employee_computations, 1)
        self.assertEqual(nb_admin_computations, 0)

        # Admin deletes this mission
        make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.cancel_mission,
            unexposed_query=False,
            variables={
                "missionId": long_mission.id,
                "userId": self.employee.id,
            },
        )

        # There should be one computation employee and admin
        (
            nb_employee_computations,
            nb_admin_computations,
        ) = self._get_computations_nb_for_date("2024-10-7")
        self.assertEqual(nb_employee_computations, 1)
        self.assertEqual(nb_admin_computations, 1)
