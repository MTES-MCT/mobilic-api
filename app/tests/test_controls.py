from app import db
from app.models import Vehicle
from app.models.activity import ActivityType
from app.models.controller_control import ControllerControl
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    ControllerFactory,
)
from app.seed.helpers import get_time
from app.tests import BaseTest
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestControls(BaseTest):
    def setUp(self):
        super().setUp()
        self.company1 = CompanyFactory.create(usual_name="Company 1")
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
            registration_number=f"XXX-001-ABC",
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
        self.controller_user = ControllerFactory.create(
            email="controller@test.com"
        )
        db.session.commit()

    def test_control_current_mission(self):

        ## GIVEN an employee has a current activity
        create_mission_response = make_authenticated_request(
            time=None,
            submitter_id=self.employee.id,
            query=ApiRequests.create_mission,
            variables={
                "company_id": self.company1.id,
                "vehicle_id": self.vehicle1.id,
            },
        )
        mission_id = create_mission_response["data"]["activities"][
            "createMission"
        ]["id"]

        start_time = get_time(how_many_days_ago=1, hour=10)
        make_authenticated_request(
            time=None,
            submitter_id=self.employee.id,
            query=ApiRequests.log_activity,
            variables=dict(
                start_time=start_time,
                end_time=None,
                mission_id=mission_id,
                type=ActivityType.DRIVE,
                user_id=self.employee.id,
                switch=False,
            ),
            request_should_fail_with=None,
        )

        # WHEN he gets controlled
        ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user.id,
            user_id=self.employee.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )

        # THEN a control is created with correct vehicle name and company name
        controls = ControllerControl.query.all()
        self.assertEqual(len(controls), 1)
        self.assertEqual(controls[0].company_name, "Company 1")
        self.assertEqual(
            controls[0].vehicle_registration_number, "XXX-001-ABC"
        )
