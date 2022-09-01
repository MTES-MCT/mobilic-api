from datetime import datetime

from app import db
from app.models.controller_control import ControllerControl
from app.seed import ControllerUserFactory, UserFactory
from app.seed.factories import ControllerControlFactory
from app.seed.helpers import get_time
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests


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

    def query_controller_info(self, controller):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=controller.id,
            query=ApiRequests.get_controller_user_info,
            variables=dict(
                id=controller.id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        return response["data"]["controllerUser"]

    def test_load_controller_info_no_controls(self):
        ## WHEN I query controller user info
        response_data = self.query_controller_info(self.controller_user_1)

        ## THEN I get a response
        self.assertIsNotNone(response_data)

        self.assertEqual(response_data["id"], self.controller_user_1.id)
        self.assertIsNone(response_data["controls"])

    def test_load_controller_info_one_control(self):
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user_1.id,
            user_id=self.controlled_user.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )

        response_data = self.query_controller_info(self.controller_user_1)

        self.assertIsNone(response_data["controls"])
