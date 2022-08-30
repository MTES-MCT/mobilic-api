from datetime import datetime

from app.seed import UserFactory
from app.seed.factories import ControllerUserFactory, ControllerControlFactory
from app.tests import BaseTest
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
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
