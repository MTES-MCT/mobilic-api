from app.domain.regulations_per_day import NATINF_32083
from app.helpers.submitter_type import SubmitterType
from app.models import RegulationCheck
from app.models.regulation_check import RegulationCheckType
from app.seed.factories import (
    RegulationComputationFactory,
    RegulatoryAlertFactory,
    ControllerControlFactory,
    ControllerUserFactory,
)
from app.seed.helpers import get_date
from app.tests.regulations import RegulationsTest

MESSAGE_EMPLOYEE = "Alerte version salarié"
MESSAGE_ADMIN = "Alerte version gestionnaire"


class TestObservedInfractions(RegulationsTest):
    def setUp(self):
        super().setUp()
        self.controller_user = ControllerUserFactory.create()

    def test_report_correct_alerts_version_at_creation(self):
        how_many_days_ago = 10

        def insert_computation(submitter_type):
            RegulationComputationFactory.create(
                day=get_date(how_many_days_ago=how_many_days_ago),
                submitter_type=submitter_type,
                user=self.employee,
            )

        def insert_alert(message, submitter_type):
            RegulatoryAlertFactory.create(
                day=get_date(how_many_days_ago=10),
                submitter_type=submitter_type,
                user=self.employee,
                regulation_check=RegulationCheck.query.filter(
                    RegulationCheck.type
                    == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
                ).first(),
                extra=dict(sanction_code=NATINF_32083, message=message),
            )

        insert_computation(submitter_type=SubmitterType.EMPLOYEE)
        insert_alert(
            message=MESSAGE_EMPLOYEE, submitter_type=SubmitterType.EMPLOYEE
        )

        control = ControllerControlFactory.create(
            user_id=self.employee.id,
            controller_id=self.controller_user.id,
        )
        control.report_infractions()
        self.assertEqual(1, len(control.observed_infractions))
        self.assertEqual(
            MESSAGE_EMPLOYEE,
            control.observed_infractions[0]["extra"]["message"],
        )

        insert_computation(submitter_type=SubmitterType.ADMIN)
        insert_alert(message=MESSAGE_ADMIN, submitter_type=SubmitterType.ADMIN)
        control.report_infractions()
        self.assertEqual(1, len(control.observed_infractions))
        self.assertEqual(
            MESSAGE_ADMIN, control.observed_infractions[0]["extra"]["message"]
        )
