from datetime import datetime

from flask.ctx import AppContext

from app import db, app
from app.models import Vehicle, Business
from app.models.activity import ActivityType
from app.models.business import BusinessType
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
        self,
        controlled_user,
        controller_user=None,
        qr_code_generation_time=None,
    ):
        if not controller_user:
            controller_user = self.controller_user_1

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
            company_id=self.company1.id,
        )
        db.session.add(self.vehicle1)
        db.session.commit()

        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

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

    def _convert_employee_to_trm_short_distance(self):
        trm_short_distance_business = Business.query.filter(
            Business.business_type == BusinessType.SHORT_DISTANCE.value
        ).one_or_none()
        self.employee_1.employments[0].business = trm_short_distance_business
        db.session.commit()

    def _convert_employee_to_trm_long_distance(self):
        trm_long_distance_business = Business.query.filter(
            Business.business_type == BusinessType.LONG_DISTANCE.value
        ).one_or_none()
        self.employee_1.employments[0].business = trm_long_distance_business
        db.session.commit()

    def _log_drive_in_mission(
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
