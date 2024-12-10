from app.seed.helpers import get_time, get_date
from app.tests.controls import ControlsTestSimple


class TestGetControllerUserInfo(ControlsTestSimple):
    def test_load_controller_info_no_controls(self):
        ## WHEN I query controller user info
        response_data = self._query_controller_info(self.controller_user_1)

        ## THEN I get a response
        self.assertIsNotNone(response_data)

        self.assertEqual(response_data["id"], self.controller_user_1.id)
        self.assertEquals(len(response_data["controls"]), 0)

    def test_load_controller_info_controls(self):
        self._create_control(self.controlled_user_1, self.controller_user_1)
        self._create_control(
            self.controlled_user_1,
            self.controller_user_1,
            get_time(how_many_days_ago=2, hour=10),
        )
        self._create_control(self.controlled_user_2, self.controller_user_1)

        response_data = self._query_controller_info(self.controller_user_1)

        self.assertIsNotNone(response_data["controls"])
        self.assertEquals(len(response_data["controls"]), 3)

    def test_retrieves_only_own_controls(self):
        self._create_control(self.controlled_user_1, self.controller_user_1)
        self._create_control(self.controlled_user_1, self.controller_user_2)

        response_data = self._query_controller_info(self.controller_user_1)

        self.assertIsNotNone(response_data["controls"])
        self.assertEquals(len(response_data["controls"]), 1)

    def test_retrieves_only_controls_after_from_date(self):
        for days_ago in range(1, 20):
            self._create_control(
                self.controlled_user_1,
                self.controller_user_1,
                get_time(how_many_days_ago=days_ago, hour=9),
            )
        response_data = self._query_controller_info(
            self.controller_user_1,
            get_date(how_many_days_ago=5).strftime("%Y-%m-%d"),
        )

        self.assertIsNotNone(response_data["controls"])
        self.assertEquals(len(response_data["controls"]), 5)
