from datetime import datetime

from app.helpers.submitter_type import SubmitterType
from app.seed import UserFactory
from app.seed.factories import (
    ControllerControlFactory,
    ControllerUserFactory,
    RegulationComputationFactory,
    RegulatoryAlertFactory,
)
from app.seed.helpers import get_date
from app.tests import BaseTest
from app.tests.helpers import (
    ApiRequests,
    make_authenticated_request,
    init_regulation_checks_data,
)


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

        regulation_check = init_regulation_checks_data()

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
            query=ApiRequests.read_control_data_with_alerts,
            variables=dict(
                control_id=control_id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        regulations_by_day = response["data"]["controlData"][
            "regulationComputationsByDay"
        ]
        self.assertEqual(len(regulations_by_day), 1)

        first_day_regulations = regulations_by_day[0]["regulationComputations"]
        self.assertEqual(
            len(first_day_regulations[0]["regulationChecks"]),
            6,
        )
        self.assertIsNotNone(
            first_day_regulations[0]["regulationChecks"][0]["alert"]
        )
        self.assertIsNone(
            first_day_regulations[0]["regulationChecks"][1]["alert"]
        )
