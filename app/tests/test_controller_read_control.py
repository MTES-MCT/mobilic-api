from datetime import datetime

from app.helpers.submitter_type import SubmitterType
from app.models.regulation_check import RegulationCheck
from app.seed import UserFactory
from app.seed.factories import (
    ControllerControlFactory,
    ControllerUserFactory,
    RegulationComputationFactory,
    RegulatoryAlertFactory,
)
from app.seed.helpers import get_date
from app.services.get_regulation_checks import get_regulation_checks
from app.tests import BaseTest
from app.tests.helpers import ApiRequests, make_authenticated_request
from app.tests.test_regulations import insert_regulation_check


class TestControllerReadControl(BaseTest):
    def setUp(self):
        super().setUp()
        self.controller_user_1 = ControllerUserFactory.create()
        self.controller_user_2 = ControllerUserFactory.create()
        self.controlled_user = UserFactory.create()

    def create_controller_control(self, controller_user):
        controller_control = ControllerControlFactory.create(
            user_id=self.controlled_user.id, controller_id=controller_user.id
        )
        return controller_control.id

    def test_read_control_data(self):
        control_id = self.create_controller_control(self.controller_user_1)
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.read_control_data,
            variables=dict(
                control_id=control_id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertEqual(response["data"]["controlData"]["id"], control_id)

    def test_can_not_read_control_of_other_controller(self):
        control_id = self.create_controller_control(self.controller_user_2)
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.read_control_data,
            variables=dict(
                control_id=control_id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertEqual(
            response["errors"][0]["extensions"]["code"], "AUTHORIZATION_ERROR"
        )

    def test_can_read_alerts(self):
        RegulationComputationFactory.create(
            day=get_date(how_many_days_ago=30),
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.controlled_user,
        )

        RegulationComputationFactory.create(
            day=get_date(how_many_days_ago=1),
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.controlled_user,
        )

        regulation_check = RegulationCheck.query.first()
        if not regulation_check:
            regulation_checks = get_regulation_checks()
            for r in regulation_checks:
                insert_regulation_check(r)
            regulation_check = RegulationCheck.query.first()

        RegulatoryAlertFactory.create(
            day=get_date(how_many_days_ago=1),
            submitter_type=SubmitterType.EMPLOYEE,
            user=self.controlled_user,
            regulation_check=regulation_check,
        )

        control_id = self.create_controller_control(self.controller_user_1)
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.read_control_data,
            variables=dict(
                control_id=control_id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        self.assertEqual(
            len(response["data"]["controlData"]["regulationComputations"]), 1
        )
        self.assertEqual(
            len(
                response["data"]["controlData"]["regulationComputations"][0][
                    "regulationChecks"
                ]
            ),
            5,
        )
        self.assertIsNotNone(
            response["data"]["controlData"]["regulationComputations"][0][
                "regulationChecks"
            ][0]["alert"]
        )
