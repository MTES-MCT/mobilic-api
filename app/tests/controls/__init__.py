from datetime import datetime

from app import db
from app.models import Vehicle
from app.seed import ControllerUserFactory, UserFactory, CompanyFactory
from app.seed.factories import ControllerControlFactory
from app.tests import BaseTest
from app.tests.helpers import (
    init_regulation_checks_data,
    init_businesses_data,
    make_authenticated_request,
    ApiRequests,
)

COMPANY_NAME_1 = "Company 1"
VEHICLE_ID_1 = "AAA 1"


class ControlsTestSimple(BaseTest):
    def setUp(self):
        super().setUp()
        init_regulation_checks_data()
        init_businesses_data()
        self.controller_user_1 = ControllerUserFactory.create()
        self.controller_user_2 = ControllerUserFactory.create()
        self.controlled_user_1 = UserFactory.create()
        self.controlled_user_2 = UserFactory.create()

    def _create_control(
        self, controller_user, controlled_user, qr_code_generation_time=None
    ):
        controller_control = (
            ControllerControlFactory.create(
                user_id=controlled_user.id,
                controller_id=controller_user.id,
                qr_code_generation_time=qr_code_generation_time,
                creation_time=qr_code_generation_time,
            )
            if qr_code_generation_time
            else ControllerControlFactory.create(
                user_id=controlled_user.id, controller_id=controller_user.id
            )
        )
        return controller_control.id

    def _query_controller_info(self, controller, from_date=None):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=controller.id,
            query=ApiRequests.get_controller_user_info,
            variables=dict(id=controller.id, from_date=from_date),
            request_by_controller_user=True,
            unexposed_query=True,
        )
        return response["data"]["controllerUser"]


class ControlsTest(ControlsTestSimple):
    def setUp(self):
        super().setUp()

        self.company1 = CompanyFactory.create(usual_name=COMPANY_NAME_1)
        self.employee_1 = UserFactory.create(
            first_name="Tim", last_name="Leader", post__company=self.company1
        )
        self.admin_1 = UserFactory.create(
            post__company=self.company1, post__has_admin_rights=True
        )
        self.vehicle1 = Vehicle(
            registration_number=VEHICLE_ID_1,
            alias=f"Vehicule 1",
            submitter=self.admin_1,
            company_id=self.company1.id,
        )
        db.session.add(self.vehicle1)
        db.session.commit()

    def _create_mission(self, employee, company, vehicle, time=None):
        create_mission_response = make_authenticated_request(
            time=time,
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
