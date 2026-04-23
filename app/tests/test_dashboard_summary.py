from datetime import datetime, date, time, timezone, timedelta

from app import db
from app.models import MissionEnd, MissionValidation
from app.models.activity import ActivityType
from app.models.employment import EmploymentRequestValidationStatus
from app.seed import CompanyFactory, UserFactory, EmploymentFactory
from app.seed.factories import ActivityFactory, MissionFactory
from app.tests import BaseTest, test_post_graphql


DASHBOARD_SUMMARY_QUERY = """
    query ($id: Int!) {
        company(id: $id) {
            dashboardSummary {
                activeMissionsCount
                pendingValidationsCount
                pendingInvitationsCount
                inactiveEmployeesCount
                autoValidatedMissionsCount
            }
        }
    }
"""


class TestDashboardSummary(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.employee = UserFactory.create(
            post__company=self.company,
        )
        self.now = datetime.now(tz=timezone.utc)

    def _query(self, user=None):
        return test_post_graphql(
            DASHBOARD_SUMMARY_QUERY,
            mock_authentication_with_user=user or self.admin,
            variables=dict(id=self.company.id),
        )

    def _get_summary(self, response):
        return response.json["data"]["company"]["dashboardSummary"]

    def _create_mission_with_activity(self, user=None):
        user = user or self.employee
        mission = MissionFactory.create(
            company_id=self.company.id,
            submitter_id=user.id,
            reception_time=self.now,
        )
        ActivityFactory.create(
            mission=mission,
            user=user,
            submitter=user,
            type=ActivityType.DRIVE,
            reception_time=self.now,
            start_time=self.now,
            last_update_time=self.now,
        )
        return mission

    def _end_mission(self, mission, user=None):
        user = user or self.employee
        db.session.add(
            MissionEnd(
                submitter=user,
                reception_time=self.now,
                user=user,
                mission=mission,
            )
        )
        db.session.commit()

    def _validate_mission(self, mission, is_auto=False, user=None):
        db.session.add(
            MissionValidation(
                submitter=self.admin if not is_auto else None,
                mission=mission,
                user=user,
                reception_time=self.now,
                is_admin=True,
                is_auto=is_auto,
            )
        )
        db.session.commit()

    def test_empty_dashboard(self):
        response = self._query()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json.get("errors"))
        data = self._get_summary(response)
        self.assertEqual(data["activeMissionsCount"], 0)
        self.assertEqual(data["pendingValidationsCount"], 0)
        self.assertEqual(data["pendingInvitationsCount"], 0)
        # only non-admin employee counted as inactive (admin excluded)
        self.assertEqual(data["inactiveEmployeesCount"], 1)
        self.assertEqual(data["autoValidatedMissionsCount"], 0)

    def test_active_missions_count(self):
        self._create_mission_with_activity()
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["activeMissionsCount"], 1)

    def test_ended_mission_not_active(self):
        mission = self._create_mission_with_activity()
        self._end_mission(mission)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["activeMissionsCount"], 0)

    def test_pending_validations_count(self):
        mission = self._create_mission_with_activity()
        self._end_mission(mission)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 1)

    def test_validated_mission_not_pending(self):
        mission = self._create_mission_with_activity()
        self._end_mission(mission)
        self._validate_mission(mission)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingValidationsCount"], 0)

    def test_pending_invitations_count(self):
        EmploymentFactory.create(
            company=self.company,
            submitter=self.admin,
            user=None,
            validation_status=EmploymentRequestValidationStatus.PENDING,
            email="invite@test.com",
        )
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["pendingInvitationsCount"], 1)

    def test_inactive_employees_with_activity(self):
        self._create_mission_with_activity(user=self.employee)
        response = self._query()
        data = self._get_summary(response)
        # employee has activity today → 0 inactive (admin excluded from count)
        self.assertEqual(data["inactiveEmployeesCount"], 0)

    def test_auto_validated_missions_count(self):
        mission = self._create_mission_with_activity()
        self._end_mission(mission)
        self._validate_mission(mission, is_auto=True, user=self.employee)
        response = self._query()
        data = self._get_summary(response)
        self.assertEqual(data["autoValidatedMissionsCount"], 1)
        # auto-validated = not pending
        self.assertEqual(data["pendingValidationsCount"], 0)

    def test_non_admin_cannot_access(self):
        other_user = UserFactory.create()
        response = self._query(user=other_user)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json.get("errors"))
