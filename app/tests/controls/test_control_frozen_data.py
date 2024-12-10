from datetime import datetime, timedelta

from app.models.activity import ActivityType
from app.tests.controls import ControlsTest
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
)


class TestControlFrozenData(ControlsTest):
    def begin_mission(self, time):
        return self._create_mission(
            employee=self.employee_1,
            company=self.company1,
            vehicle=self.vehicle1,
            time=time,
        )

    def begin_activity(self, time, mission_id):
        response = make_authenticated_request(
            time=time,
            submitter_id=self.employee_1.id,
            query=ApiRequests.log_activity,
            variables=dict(
                start_time=time,
                mission_id=mission_id,
                type=ActivityType.WORK,
                user_id=self.employee_1.id,
                switch=True,
            ),
        )
        activity_id = response["data"]["activities"]["logActivity"]["id"]
        return activity_id

    def end_activity(self, time, activity_id):
        make_authenticated_request(
            time=time,
            submitter_id=self.employee_1.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activity_id=activity_id,
                end_time=time,
            ),
        )

    def edit_activity(self, time, start_time, end_time, activity_id):
        make_authenticated_request(
            time=time,
            submitter_id=self.employee_1.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activity_id=activity_id,
                start_time=start_time,
                end_time=end_time,
            ),
        )

    def create_controller_control(
        self, controller_user, qr_code_generation_time
    ):
        return self._create_control(
            controller_user=controller_user,
            controlled_user=self.employee_1,
            qr_code_generation_time=qr_code_generation_time,
        )

    def test_freeze_activity_edition(self):
        initial_mission_start_time = datetime(2022, 2, 18, 6, 0, 0)
        initial_mission_end_time = initial_mission_start_time + timedelta(
            hours=1
        )
        mission_id = self.begin_mission(initial_mission_start_time)
        activity_id = self.begin_activity(
            initial_mission_start_time, mission_id
        )
        self.end_activity(initial_mission_end_time, activity_id)
        control_id = self.create_controller_control(
            self.controller_user_1,
            qr_code_generation_time=initial_mission_end_time,
        )
        self.edit_activity(
            initial_mission_end_time + timedelta(days=1),
            initial_mission_start_time + timedelta(minutes=5),
            initial_mission_end_time + timedelta(minutes=5),
            activity_id,
        )
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
            datetime.fromtimestamp(
                response["data"]["controlData"]["missions"][0]["activities"][
                    0
                ]["startTime"]
            ),
            initial_mission_start_time,
        )
        self.assertEqual(
            datetime.fromtimestamp(
                response["data"]["controlData"]["missions"][0]["activities"][
                    0
                ]["endTime"]
            ),
            initial_mission_end_time,
        )

    def test_freeze_activity_creation(self):
        first_activity_start_time = datetime(2022, 2, 18, 6, 0, 0)
        first_activity_end_time = first_activity_start_time + timedelta(
            hours=1
        )
        second_activity_start_time = first_activity_end_time + timedelta(
            hours=2
        )
        second_activity_end_time = second_activity_start_time + timedelta(
            hours=1
        )

        mission_id = self.begin_mission(first_activity_start_time)

        first_activity_id = self.begin_activity(
            first_activity_start_time, mission_id
        )
        self.end_activity(first_activity_end_time, first_activity_id)

        control_id = self.create_controller_control(
            self.controller_user_1,
            qr_code_generation_time=first_activity_end_time,
        )

        second_activity_id = self.begin_activity(
            second_activity_start_time, mission_id
        )
        self.end_activity(second_activity_end_time, second_activity_id)

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
            response["data"]["controlData"]["missions"][0]["activities"][0][
                "id"
            ],
            first_activity_id,
        )
        self.assertEqual(
            len(response["data"]["controlData"]["missions"][0]["activities"]),
            1,
        )
