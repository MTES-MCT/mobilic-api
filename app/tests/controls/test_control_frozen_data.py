from datetime import datetime, timedelta

from app.models.activity import ActivityType
from app.tests.controls import ControlsTest
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
)
from app import db


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

    def test_version_at_default_filters_by_reception_time(self):
        """Non-regression: version_at without include_posteriori_activities
        must filter by reception_time (historical behavior).
        """
        activity_start = datetime(2022, 3, 1, 8, 0, 0)
        activity_end = datetime(2022, 3, 1, 9, 0, 0)
        control_time = activity_end

        mission_id = self.begin_mission(activity_start)
        activity_id = self.begin_activity(activity_start, mission_id)
        self.end_activity(activity_end, activity_id)

        self.edit_activity(
            control_time + timedelta(days=1),
            activity_start + timedelta(minutes=10),
            activity_end + timedelta(minutes=10),
            activity_id,
        )

        from app.models import Activity

        activity = Activity.query.get(activity_id)
        db.session.refresh(activity)

        frozen = activity.version_at(
            control_time, include_posteriori_activities=False
        )
        self.assertIsNotNone(frozen)
        self.assertEqual(frozen.start_time, activity_start)
        self.assertEqual(frozen.end_time, activity_end)

    def test_version_at_with_posteriori_includes_late_logged_activity(self):
        """Controller case: version_at with include_posteriori_activities=True
        must include an activity logged after the control but with start_time before it.
        """
        activity_start = datetime(2022, 3, 2, 8, 0, 0)
        activity_end = datetime(2022, 3, 2, 9, 0, 0)
        control_time = activity_end

        mission_id = self.begin_mission(activity_start)

        activity_id = self.begin_activity(
            control_time + timedelta(hours=1), mission_id
        )
        self.end_activity(control_time + timedelta(hours=2), activity_id)
        self.edit_activity(
            control_time + timedelta(hours=2),
            activity_start,
            activity_end,
            activity_id,
        )

        from app.models import Activity

        activity = Activity.query.get(activity_id)
        db.session.refresh(activity)

        frozen_default = activity.version_at(
            control_time, include_posteriori_activities=False
        )
        self.assertIsNone(frozen_default)

        frozen_controller = activity.version_at(
            control_time, include_posteriori_activities=True
        )
        self.assertIsNotNone(frozen_controller)

    def test_freeze_activity_at_non_regression_default_behavior(self):
        """Non-regression: freeze_activity_at without include_posteriori_activities
        must freeze to the value before the edit (filters by reception_time).
        Ensures frozen exports (C1B) and regulation alerts (DREAL) are not affected.
        """
        activity_start = datetime(2022, 3, 3, 8, 0, 0)
        activity_end = datetime(2022, 3, 3, 9, 0, 0)
        freeze_time = activity_end

        mission_id = self.begin_mission(activity_start)
        activity_id = self.begin_activity(activity_start, mission_id)
        self.end_activity(activity_end, activity_id)

        self.edit_activity(
            freeze_time + timedelta(days=1),
            activity_start + timedelta(minutes=30),
            activity_end + timedelta(minutes=30),
            activity_id,
        )

        from app.models import Activity

        activity = Activity.query.get(activity_id)
        db.session.refresh(activity)

        frozen = activity.freeze_activity_at(freeze_time)
        self.assertIsNotNone(frozen)
        self.assertEqual(frozen.start_time, activity_start)
        self.assertEqual(frozen.end_time, activity_end)
