from datetime import datetime

from app import db
from app.models.controller_control import ControllerControl
from app.seed import ControllerUserFactory, UserFactory
from app.seed.factories import ControllerControlFactory
from app.seed.helpers import get_time, get_date
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestControllerReadControl(BaseTest):
    def setUp(self):
        super().setUp()
        self.controller_user_1 = ControllerUserFactory.create()
        self.controller_user_2 = ControllerUserFactory.create()
        self.controlled_user_1 = UserFactory.create()
        self.controlled_user_2 = UserFactory.create()

    def create_controller_control(
        self,
        controller_user,
        controlled_user,
        qr_code_generation_time=datetime.now(),
    ):
        controller_control = ControllerControlFactory.create(
            user_id=controlled_user.id,
            controller_id=controller_user.id,
            qr_code_generation_time=qr_code_generation_time,
        )
        return controller_control.id

    def query_controller_info(self, controller, from_date=None):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=controller.id,
            query=ApiRequests.get_controller_user_info,
            variables=dict(id=controller.id, from_date=from_date),
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
        self.assertEquals(len(response_data["controls"]), 0)

    def test_load_controller_info_controls(self):
        self.create_controller_control(
            self.controller_user_1, self.controlled_user_1
        )
        self.create_controller_control(
            self.controller_user_1,
            self.controlled_user_1,
            get_time(how_many_days_ago=2, hour=10),
        )
        self.create_controller_control(
            self.controller_user_1, self.controlled_user_2
        )

        response_data = self.query_controller_info(self.controller_user_1)

        self.assertIsNotNone(response_data["controls"])
        self.assertEquals(len(response_data["controls"]), 3)

    def test_retrieves_only_own_controls(self):
        self.create_controller_control(
            self.controller_user_1, self.controlled_user_1
        )
        self.create_controller_control(
            self.controller_user_2, self.controlled_user_1
        )

        response_data = self.query_controller_info(self.controller_user_1)

        self.assertIsNotNone(response_data["controls"])
        self.assertEquals(len(response_data["controls"]), 1)

    def test_retrieves_only_controls_after_from_date(self):
        for days_ago in range(1, 20):
            self.create_controller_control(
                self.controller_user_1,
                self.controlled_user_1,
                get_time(how_many_days_ago=days_ago, hour=9),
            )
        response_data = self.query_controller_info(
            self.controller_user_1,
            get_date(how_many_days_ago=5).strftime("%Y-%m-%d"),
        )

        self.assertIsNotNone(response_data["controls"])
        self.assertEquals(len(response_data["controls"]), 5)
