from datetime import datetime

from app import db
from app.models import Business
from app.models.business import BusinessType
from app.models.controller_control import ControllerControl
from app.seed import CompanyFactory, EmploymentFactory
from app.seed.helpers import get_time
from app.tests.controls import ControlsTest
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestBusinessTypeInControl(ControlsTest):
    def create_mission(self):
        return self._create_mission(
            employee=self.employee_1,
            company=self.company1,
            vehicle=self.vehicle1,
        )

    def _get_control_data_(self, control):
        return make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.controller_user_1.id,
            query=ApiRequests.read_control_data,
            variables=dict(
                control_id=control.id,
            ),
            request_by_controller_user=True,
            unexposed_query=True,
        )

    def _get_control_data_business_type(self, control):
        response = self._get_control_data_(control=control)
        return response["data"]["controlData"]["businessTypeDuringControl"]

    def test_employee_controlled_without_mission_no_business_id(self):
        # When flashing an employee not currently working
        control = ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user_1.id,
            user_id=self.employee_1.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )

        # No business_id is stored in the control bulletin
        self.assertIsNone(control.control_bulletin.get("business_id"))

        control_business_type = self._get_control_data_business_type(
            control=control
        )
        self.assertIsNone(control_business_type)

    def test_employee_controlled_with_mission_correct_business_id(self):
        # An employee has a current mission for SHORT_DISTANCE
        self._convert_employee_to_trm_short_distance()
        mission_id = self.create_mission()
        start_time = get_time(how_many_days_ago=1, hour=10)
        end_time = get_time(how_many_days_ago=1, hour=11)
        self._log_drive_in_mission(
            mission_id, self.employee_1, start_time, end_time
        )

        control = ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user_1.id,
            user_id=self.employee_1.id,
            qr_code_generation_time=get_time(how_many_days_ago=1, hour=11),
        )
        self.assertIsNotNone(control.control_bulletin.get("business_id"))

        # control data shows business type at control time
        control_business_type = self._get_control_data_business_type(
            control=control
        )
        self.assertEqual(
            control_business_type["businessType"],
            BusinessType.SHORT_DISTANCE.name,
        )

        # even if employee change business type after that
        self._convert_employee_to_trm_long_distance()
        control_business_type = self._get_control_data_business_type(
            control=control
        )
        self.assertEqual(
            control_business_type["businessType"],
            BusinessType.SHORT_DISTANCE.name,
        )

    def test_employee_with_several_employments_correct_business_types(self):
        company2 = CompanyFactory.create(usual_name="Company 2")
        EmploymentFactory.create(
            company=company2,
            submitter=self.admin_1,
            user=self.admin_1,
            has_admin_rights=True,
        )
        EmploymentFactory.create(
            company=company2,
            submitter=self.admin_1,
            user=self.employee_1,
            has_admin_rights=False,
        )
        trm_short_distance_business = Business.query.filter(
            Business.business_type == BusinessType.SHORT_DISTANCE.value
        ).one_or_none()
        trm_long_distance_business = Business.query.filter(
            Business.business_type == BusinessType.LONG_DISTANCE.value
        ).one_or_none()
        vtc_business = Business.query.filter(
            Business.business_type == BusinessType.VTC.value
        ).one_or_none()

        employments = self.employee_1.employments
        for e in employments:
            if e.company.name == self.company1.name:
                e.business = trm_short_distance_business
            else:
                e.business = trm_long_distance_business
        db.session.commit()

        control = ControllerControl.get_or_create_mobilic_control(
            controller_id=self.controller_user_1.id,
            user_id=self.employee_1.id,
            qr_code_generation_time=datetime.now(),
        )

        employments[0].business = vtc_business
        employments[1].business = vtc_business
        db.session.commit()

        response = self._get_control_data_(control=control)
        response_employments = response["data"]["controlData"]["employments"]
        for e in response_employments:
            if e["company"]["name"] == self.company1.name:
                self.assertEqual(
                    e["business"]["businessType"],
                    BusinessType.SHORT_DISTANCE.name,
                )
            else:
                self.assertEqual(
                    e["business"]["businessType"],
                    BusinessType.LONG_DISTANCE.name,
                )
