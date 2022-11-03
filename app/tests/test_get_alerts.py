from app.helpers.submitter_type import SubmitterType
from app.models.regulation_check import RegulationCheck
from app.seed import CompanyFactory, UserFactory
from app.seed.factories import (
    EmploymentFactory,
    RegulationComputationFactory,
    RegulatoryAlertFactory,
)
from app.seed.helpers import get_date
from app.services.get_regulation_checks import get_regulation_checks
from app.tests import BaseTest, test_post_graphql
from app.tests.helpers import ApiRequests
from app.tests.test_regulations import insert_regulation_check

ADMIN_EMAIL = "admin@email.com"
EMPLOYEE_EMAIL = "employee@email.com"


class TestGetAlerts(BaseTest):
    def setUp(self):
        super().setUp()

        regulation_check = RegulationCheck.query.first()
        if not regulation_check:
            regulation_checks = get_regulation_checks()
            for r in regulation_checks:
                insert_regulation_check(r)
            regulation_check = RegulationCheck.query.first()

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

        RegulationComputationFactory.create(
            day=get_date(how_many_days_ago=2),
            submitter_type=SubmitterType.EMPLOYEE,
            user=employee,
        )

        RegulationComputationFactory.create(
            day=get_date(how_many_days_ago=1),
            submitter_type=SubmitterType.EMPLOYEE,
            user=employee,
        )

        RegulatoryAlertFactory.create(
            day=get_date(how_many_days_ago=1),
            submitter_type=SubmitterType.EMPLOYEE,
            user=employee,
            regulation_check=regulation_check,
        )

        self.company = company
        self.admin = admin
        self.employee = employee

    def test_user_can_access_his_own_alerts(self):
        response = test_post_graphql(
            ApiRequests.get_alerts,
            mock_authentication_with_user=self.employee,
            variables=dict(
                userId=self.employee.id,
                day=get_date(how_many_days_ago=1).strftime("%Y-%m-%d"),
                submitterType=SubmitterType.EMPLOYEE,
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json.get("errors"))
