from datetime import datetime

from flask.ctx import AppContext

from app import app, db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import Mission, Business
from app.models.activity import ActivityType
from app.models.business import BusinessType
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    AuthenticatedUserContext,
)
from app.tests import BaseTest
from app.tests.helpers import init_regulation_checks_data, init_businesses_data

ADMIN_EMAIL = "admin@email.com"
EMPLOYEE_EMAIL = "employee@email.com"


class RegulationsTest(BaseTest):
    def setUp(self):
        super().setUp()

        init_regulation_checks_data()
        init_businesses_data()

        company = CompanyFactory.create(
            usual_name="Company Name", siren="1122334", allow_transfers=True
        )

        admin = UserFactory.create(
            email=ADMIN_EMAIL,
            password="password",
            first_name="Admin",
            last_name="Admin",
        )
        EmploymentFactory.create(
            company=company, submitter=admin, user=admin, has_admin_rights=True
        )

        employee = UserFactory.create(
            email=EMPLOYEE_EMAIL,
            password="password",
        )
        EmploymentFactory.create(
            company=company,
            submitter=admin,
            user=employee,
            has_admin_rights=False,
        )

        self.company = company
        self.admin = admin
        self.employee = employee
        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _log_and_validate_mission(
        self,
        mission_name,
        submitter,
        work_periods,
        company=None,
        reception_time=None,
    ):
        mission = Mission(
            name=mission_name,
            company=company if company else self.company,
            reception_time=reception_time
            if reception_time
            else datetime.now(),
            submitter=submitter,
        )
        db.session.add(mission)
        db.session.commit()

        with AuthenticatedUserContext(user=submitter):
            for work_period in work_periods:
                log_activity(
                    submitter=submitter,
                    user=submitter,
                    mission=mission,
                    type=work_period[2]
                    if len(work_period) >= 3
                    else ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=work_period[1],
                    start_time=work_period[0],
                    end_time=work_period[1],
                )
            validate_mission(
                submitter=submitter, mission=mission, for_user=submitter
            )
        return mission

    def _convert_employee_to_business(self, business_type):
        business = Business.query.filter(
            Business.business_type == business_type.value
        ).one_or_none()
        self.employee.employments[0].business = business
        db.session.commit()

    def convert_employee_to_vtc(self):
        self._convert_employee_to_business(BusinessType.VTC)

    def convert_employee_to_trv(self):
        self._convert_employee_to_business(BusinessType.FREQUENT)

    def convert_employee_to_trm_short_distance(self):
        self._convert_employee_to_business(BusinessType.SHORT_DISTANCE)
