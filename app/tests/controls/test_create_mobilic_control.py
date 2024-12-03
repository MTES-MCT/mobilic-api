from app.models.controller_control import ControllerControl
from app.seed.helpers import get_time
from app.tests.controls import ControlsTest, COMPANY_NAME_1, VEHICLE_ID_1
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestCreateMobilicControl(ControlsTest):
    def create_mission(self):
        return self._create_mission(
            employee=self.employee_1,
            company=self.company1,
            vehicle=self.vehicle1,
        )

    def end_mission(self, mission_id, end_time, user_id):
        make_authenticated_request(
            time=end_time,
            submitter_id=user_id,
            query=ApiRequests.end_mission,
            variables=dict(
                end_time=end_time,
                mission_id=mission_id,
                user_id=user_id,
            ),
        )

    def control_user_during_work(self):
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user_1.id,
            user_id=self.employee_1.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )

    def control_user_after_work(self):
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user_1.id,
            user_id=self.employee_1.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=14),
        )

    def test_control_current_mission(self):
        ## GIVEN an employee has a current activity
        mission_id = self.create_mission()

        start_time = get_time(how_many_days_ago=1, hour=10)
        self._log_drive_in_mission(mission_id, self.employee_1, start_time)

        # WHEN he gets controlled
        self.control_user_during_work()

        # THEN a control is created with correct vehicle name and company name
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].company_name, COMPANY_NAME_1)
        self.assertEqual(controls[0].vehicle_registration_number, VEHICLE_ID_1)

    def test_control_has_correct_nb_controlled_days(self):
        ## GIVEN an employee has worked 3 different days in the past 28 days
        for days_ago in [8, 6, 4]:
            mission_id = self.create_mission()
            start_time = get_time(how_many_days_ago=days_ago, hour=10)
            end_time = get_time(how_many_days_ago=days_ago, hour=11)
            self._log_drive_in_mission(
                mission_id, self.employee_1, start_time, end_time
            )

        ## WHEN he gets controlled
        self.control_user_during_work()

        ## THEN control should have 3 nb_controlled_days
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].nb_controlled_days, 3)

    def test_control_nb_controlled_days_ignores_too_old_activity(self):
        ## GIVEN an employee has worked 2 months ago
        mission_id = self.create_mission()
        start_time = get_time(how_many_days_ago=64, hour=10)
        end_time = get_time(how_many_days_ago=64, hour=11)
        self._log_drive_in_mission(
            mission_id, self.employee_1, start_time, end_time
        )

        ## WHEN he gets controlled
        self.control_user_during_work()

        ## THEN control should have 0 nb_controlled_days
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].nb_controlled_days, 0)

    def test_control_nb_controlled_days_two_missions_same_day(self):
        ## GIVEN an employee has worked two missions on the same day
        mission_id = self.create_mission()
        start_time1 = get_time(how_many_days_ago=4, hour=10)
        end_time1 = get_time(how_many_days_ago=4, hour=11)
        self._log_drive_in_mission(
            mission_id, self.employee_1, start_time1, end_time1
        )
        start_time2 = get_time(how_many_days_ago=4, hour=16)
        end_time2 = get_time(how_many_days_ago=4, hour=17)
        self._log_drive_in_mission(
            mission_id, self.employee_1, start_time2, end_time2
        )

        ## WHEN he gets controlled
        self.control_user_during_work()

        ## THEN control should have only 1 nb_controlled_days
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].nb_controlled_days, 1)

    def test_control_nb_controlled_days_overlapping_mission(self):
        ## GIVEN an employee has worked on a mission overlapping two days
        mission_id = self.create_mission()
        start_time = get_time(how_many_days_ago=4, hour=20)
        end_time = get_time(how_many_days_ago=3, hour=5)
        self._log_drive_in_mission(
            mission_id, self.employee_1, start_time, end_time
        )

        ## WHEN he gets controlled
        self.control_user_during_work()

        ## THEN control should have 2 nb_controlled_days
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].nb_controlled_days, 2)

    def test_control_company_name_vehicle_id_while_in_break(self):

        ## GIVEN an employee is in break
        mission_id = self.create_mission()

        start_time = get_time(how_many_days_ago=1, hour=10)
        end_time = get_time(how_many_days_ago=1, hour=11)
        self._log_drive_in_mission(
            mission_id, self.employee_1, start_time, end_time=end_time
        )

        # WHEN he gets controlled
        self.control_user_after_work()

        # THEN a control is created with correct vehicle name and company name
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].company_name, COMPANY_NAME_1)
        self.assertEqual(controls[0].vehicle_registration_number, VEHICLE_ID_1)

    def test_control_company_name_vehicle_id_empty_if_mission_ended(self):

        ## GIVEN an employee has ended his mission for the day
        mission_id = self.create_mission()

        start_time = get_time(how_many_days_ago=1, hour=10)
        end_time = get_time(how_many_days_ago=1, hour=11)
        self._log_drive_in_mission(
            mission_id, self.employee_1, start_time, end_time=end_time
        )
        self.end_mission(
            mission_id,
            get_time(how_many_days_ago=1, hour=13),
            self.employee_1.id,
        )

        # WHEN he gets controlled
        self.control_user_after_work()

        # THEN a control is created with correct vehicle name and company name
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].company_name, "")
        self.assertEqual(controls[0].vehicle_registration_number, "")
