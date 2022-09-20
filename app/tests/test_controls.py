from app import db
from app.models import Vehicle
from app.models.activity import ActivityType
from app.models.controller_control import ControllerControl
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    ControllerUserFactory,
)
from app.seed.helpers import get_time
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests


COMPANY_NAME_1 = "Company 1"
VEHICLE_ID_1 = "Company 1"


class TestControls(BaseTest):
    def setUp(self):
        super().setUp()
        self.company1 = CompanyFactory.create(usual_name=COMPANY_NAME_1)
        self.company2 = CompanyFactory.create(usual_name="Company 2")
        self.admin1 = UserFactory.create(
            post__company=self.company1, post__has_admin_rights=True
        )
        self.admin2 = UserFactory.create(
            post__company=self.company2, post__has_admin_rights=True
        )
        self.employee = UserFactory.create()
        EmploymentFactory.create(
            company=self.company1,
            submitter=self.admin1,
            user=self.employee,
            has_admin_rights=False,
        )
        EmploymentFactory.create(
            company=self.company2,
            submitter=self.admin2,
            user=self.employee,
            has_admin_rights=False,
        )
        self.vehicle1 = Vehicle(
            registration_number=VEHICLE_ID_1,
            alias=f"Vehicule 1",
            submitter=self.admin1,
            company_id=self.company1.id,
        )
        self.vehicle2 = Vehicle(
            registration_number=f"XXX-002-ABC",
            alias=f"Vehicule 2",
            submitter=self.admin2,
            company_id=self.company2.id,
        )
        db.session.add(self.vehicle2)
        db.session.add(self.vehicle1)
        self.controller_user = ControllerUserFactory.create(
            email="controller@test.com"
        )
        db.session.commit()

    def create_mission(self, employee, company, vehicle):
        create_mission_response = make_authenticated_request(
            time=None,
            submitter_id=employee.id,
            query=ApiRequests.create_mission,
            variables={
                "company_id": company.id,
                "vehicle_id": vehicle.id,
            },
        )
        return create_mission_response["data"]["activities"]["createMission"][
            "id"
        ]

    def log_drive_in_mission(
        self, mission_id, employee, start_time, end_time=None
    ):
        make_authenticated_request(
            time=None,
            submitter_id=employee.id,
            query=ApiRequests.log_activity,
            variables=dict(
                start_time=start_time,
                end_time=end_time,
                mission_id=mission_id,
                type=ActivityType.DRIVE,
                user_id=employee.id,
                switch=False,
            ),
            request_should_fail_with=None,
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

    def test_control_current_mission(self):

        ## GIVEN an employee has a current activity
        mission_id = self.create_mission(
            self.employee, self.company1, self.vehicle1
        )

        start_time = get_time(how_many_days_ago=1, hour=10)
        self.log_drive_in_mission(mission_id, self.employee, start_time)

        # WHEN he gets controlled
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user.id,
            user_id=self.employee.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )

        # THEN a control is created with correct vehicle name and company name
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].company_name, COMPANY_NAME_1)
        self.assertEqual(controls[0].vehicle_registration_number, VEHICLE_ID_1)

    def test_control_has_correct_nb_controlled_days(self):
        ## GIVEN an employee has worked 3 different days in the past 28 days
        for days_ago in [8, 6, 4]:
            mission_id = self.create_mission(
                self.employee, self.company1, self.vehicle1
            )
            start_time = get_time(how_many_days_ago=days_ago, hour=10)
            end_time = get_time(how_many_days_ago=days_ago, hour=11)
            self.log_drive_in_mission(
                mission_id, self.employee, start_time, end_time
            )

        ## WHEN he gets controlled
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user.id,
            user_id=self.employee.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )

        ## THEN control should have 3 nb_controlled_days
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].nb_controlled_days, 3)

    def test_control_nb_controlled_days_ignores_too_old_activity(self):
        ## GIVEN an employee has worked 2 months ago
        mission_id = self.create_mission(
            self.employee, self.company1, self.vehicle1
        )
        start_time = get_time(how_many_days_ago=64, hour=10)
        end_time = get_time(how_many_days_ago=64, hour=11)
        self.log_drive_in_mission(
            mission_id, self.employee, start_time, end_time
        )

        ## WHEN he gets controlled
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user.id,
            user_id=self.employee.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )

        ## THEN control should have 0 nb_controlled_days
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].nb_controlled_days, 0)

    def test_control_nb_controlled_days_two_missions_same_day(self):
        ## GIVEN an employee has worked two missions on the same day
        mission_id = self.create_mission(
            self.employee, self.company1, self.vehicle1
        )
        start_time1 = get_time(how_many_days_ago=4, hour=10)
        end_time1 = get_time(how_many_days_ago=4, hour=11)
        self.log_drive_in_mission(
            mission_id, self.employee, start_time1, end_time1
        )
        start_time2 = get_time(how_many_days_ago=4, hour=16)
        end_time2 = get_time(how_many_days_ago=4, hour=17)
        self.log_drive_in_mission(
            mission_id, self.employee, start_time2, end_time2
        )

        ## WHEN he gets controlled
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user.id,
            user_id=self.employee.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )

        ## THEN control should have only 1 nb_controlled_days
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].nb_controlled_days, 1)

    def test_control_nb_controlled_days_overlapping_mission(self):
        ## GIVEN an employee has worked on a mission overlapping two days
        mission_id = self.create_mission(
            self.employee, self.company1, self.vehicle1
        )
        start_time = get_time(how_many_days_ago=4, hour=20)
        end_time = get_time(how_many_days_ago=3, hour=5)
        self.log_drive_in_mission(
            mission_id, self.employee, start_time, end_time
        )

        ## WHEN he gets controlled
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user.id,
            user_id=self.employee.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )

        ## THEN control should have 2 nb_controlled_days
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].nb_controlled_days, 2)

    def test_control_company_name_vehicle_id_while_in_break(self):

        ## GIVEN an employee is in break
        mission_id = self.create_mission(
            self.employee, self.company1, self.vehicle1
        )

        start_time = get_time(how_many_days_ago=1, hour=10)
        end_time = get_time(how_many_days_ago=1, hour=11)
        self.log_drive_in_mission(
            mission_id, self.employee, start_time, end_time=end_time
        )

        # WHEN he gets controlled
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user.id,
            user_id=self.employee.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=14),
        )

        # THEN a control is created with correct vehicle name and company name
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].company_name, COMPANY_NAME_1)
        self.assertEqual(controls[0].vehicle_registration_number, VEHICLE_ID_1)

    def test_control_company_name_vehicle_id_empty_if_mission_ended(self):

        ## GIVEN an employee has ended his mission for the day
        mission_id = self.create_mission(
            self.employee, self.company1, self.vehicle1
        )

        start_time = get_time(how_many_days_ago=1, hour=10)
        end_time = get_time(how_many_days_ago=1, hour=11)
        self.log_drive_in_mission(
            mission_id, self.employee, start_time, end_time=end_time
        )
        self.end_mission(
            mission_id,
            get_time(how_many_days_ago=1, hour=13),
            self.employee.id,
        )

        # WHEN he gets controlled
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user.id,
            user_id=self.employee.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=14),
        )

        # THEN a control is created with correct vehicle name and company name
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].company_name, "")
        self.assertEqual(controls[0].vehicle_registration_number, "")
