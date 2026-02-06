"""
Test suite for IDOR (Insecure Direct Object Reference) vulnerabilities
"""

from datetime import datetime, timedelta

from flask.ctx import AppContext

from app import app, db
from app.domain.log_activities import log_activity
from app.helpers.errors import AuthorizationError
from app.models import Mission
from app.models.activity import ActivityType, Activity
from app.seed import UserFactory, CompanyFactory
from app.tests import BaseTest, AuthenticatedUserContext, test_post_graphql
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestIDORVulnerabilities(BaseTest):
    def setUp(self):
        super().setUp()

        self.company_a = CompanyFactory.create()
        self.admin_a = UserFactory.create(
            post__company=self.company_a, post__has_admin_rights=True
        )
        self.worker_a = UserFactory.create(post__company=self.company_a)

        self.company_b = CompanyFactory.create()
        self.admin_b = UserFactory.create(
            post__company=self.company_b, post__has_admin_rights=True
        )
        self.worker_b = UserFactory.create(post__company=self.company_b)

        self._app_context = AppContext(app)
        self._app_context.__enter__()

        with AuthenticatedUserContext(user=self.worker_a):
            self.mission_a = Mission.create(
                submitter=self.worker_a,
                company=self.company_a,
                reception_time=datetime.now(),
            )
            self.activity_a = log_activity(
                submitter=self.worker_a,
                user=self.worker_a,
                mission=self.mission_a,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=datetime.now(),
                start_time=datetime.now() - timedelta(hours=2),
                end_time=None,
            )
        db.session.commit()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_idor_end_mission_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_b.id,
            query=ApiRequests.end_mission,
            variables=dict(
                missionId=self.mission_a.id,
                endTime=datetime.now(),
                userId=self.worker_a.id,
            ),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

        activity = Activity.query.get(self.activity_a.id)
        self.assertIsNone(activity.end_time if activity else None)

    def test_idor_end_mission_without_user_id_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_b.id,
            query=ApiRequests.end_mission,
            variables=dict(
                missionId=self.mission_a.id,
                endTime=datetime.now(),
            ),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_idor_validate_mission_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_b.id,
            query=ApiRequests.validate_mission,
            variables=dict(
                missionId=self.mission_a.id,
                usersIds=[self.worker_a.id],
            ),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_idor_cancel_mission_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_b.id,
            query=ApiRequests.cancel_mission,
            variables=dict(
                missionId=self.mission_a.id,
                userId=self.worker_a.id,
            ),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

        activity = Activity.query.get(self.activity_a.id)
        self.assertFalse(activity.is_dismissed if activity else True)

    def test_idor_change_mission_name_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_b.id,
            query=ApiRequests.change_mission_name,
            variables=dict(
                missionId=self.mission_a.id,
                name="Hacked",
            ),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_idor_update_mission_vehicle_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_b.id,
            query=ApiRequests.update_mission_vehicle,
            variables=dict(
                missionId=self.mission_a.id,
                vehicleRegistrationNumber="HACKED",
            ),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_idor_cancel_activity_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_b.id,
            query=ApiRequests.cancel_activity,
            variables=dict(activityId=self.activity_a.id),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_idor_edit_activity_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_b.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activityId=self.activity_a.id,
                startTime=datetime.now() - timedelta(hours=5),
                endTime=datetime.now(),
            ),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_idor_log_activity_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_b.id,
            query=ApiRequests.log_activity,
            variables=dict(
                type=ActivityType.DRIVE,
                startTime=datetime.now(),
                missionId=self.mission_a.id,
                userId=self.worker_b.id,
            ),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_idor_query_mission_cross_company_blocked(self):
        query = """
            query ($id: Int!) {
                mission(id: $id) {
                    id
                    name
                }
            }
        """

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_b.id,
            query=query,
            variables=dict(id=self.mission_a.id),
        )

        if "errors" in response:
            self.assertEqual(
                AuthorizationError.code,
                response["errors"][0]["extensions"]["code"],
            )
        else:
            self.assertIsNone(response.get("data", {}).get("mission"))

    def test_valid_end_mission_same_company_allowed(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_a.id,
            query=ApiRequests.end_mission,
            variables=dict(
                missionId=self.mission_a.id,
                endTime=datetime.now(),
            ),
        )

        self.assertNotIn("errors", response)
        self.assertIsNotNone(response["data"]["activities"]["endMission"])

    def test_valid_admin_can_end_worker_mission_same_company(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_a.id,
            query=ApiRequests.end_mission,
            variables=dict(
                missionId=self.mission_a.id,
                endTime=datetime.now(),
                userId=self.worker_a.id,
            ),
        )

        self.assertNotIn("errors", response)
        self.assertIsNotNone(response["data"]["activities"]["endMission"])

    def test_idor_sequential_id_enumeration_blocked(self):
        for offset in [-2, -1, 1, 2]:
            test_mission_id = self.mission_a.id + offset

            response = make_authenticated_request(
                time=datetime.now(),
                submitter_id=self.worker_b.id,
                query=ApiRequests.end_mission,
                variables=dict(
                    missionId=test_mission_id,
                    endTime=datetime.now(),
                ),
            )

            if (
                response.get("data", {})
                .get("activities", {})
                .get("endMission")
            ):
                self.fail(f"IDOR: Accessed mission {test_mission_id}")

    def test_idor_mission_with_null_user_id(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_b.id,
            query=ApiRequests.end_mission,
            variables=dict(
                missionId=self.mission_a.id,
                endTime=datetime.now(),
                userId=None,
            ),
        )

        self.assertIn("errors", response)

    def test_idor_activity_of_deleted_mission(self):
        with AuthenticatedUserContext(user=self.worker_a):
            self.activity_a.dismiss(context={"reason": "test"})
            db.session.commit()

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_b.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activityId=self.activity_a.id,
                endTime=datetime.now(),
            ),
        )

        self.assertIn("errors", response)


class TestIDORLocationEntry(BaseTest):
    def setUp(self):
        super().setUp()

        self.company_a = CompanyFactory.create()
        self.worker_a = UserFactory.create(post__company=self.company_a)

        self.company_b = CompanyFactory.create()
        self.worker_b = UserFactory.create(post__company=self.company_b)

        self._app_context = AppContext(app)
        self._app_context.__enter__()

        with AuthenticatedUserContext(user=self.worker_a):
            self.mission_a = Mission.create(
                submitter=self.worker_a,
                company=self.company_a,
                reception_time=datetime.now(),
            )
        db.session.commit()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_idor_log_location_cross_company_blocked(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_b.id,
            query=ApiRequests.log_location,
            variables=dict(
                type="mission_start_location",
                missionId=self.mission_a.id,
                manualAddress="123 Hacker Street",
            ),
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )


class TestIDORExpenditure(BaseTest):
    def setUp(self):
        super().setUp()

        self.company_a = CompanyFactory.create()
        self.worker_a = UserFactory.create(post__company=self.company_a)

        self.company_b = CompanyFactory.create()
        self.worker_b = UserFactory.create(post__company=self.company_b)

        self._app_context = AppContext(app)
        self._app_context.__enter__()

        with AuthenticatedUserContext(user=self.worker_a):
            self.mission_a = Mission.create(
                submitter=self.worker_a,
                company=self.company_a,
                reception_time=datetime.now(),
            )
        db.session.commit()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_idor_log_expenditure_cross_company_blocked(self):
        response = test_post_graphql(
            query=ApiRequests.log_expenditure,
            mock_authentication_with_user=self.worker_b,
            variables=dict(
                missionId=self.mission_a.id,
                type="day_meal",
                userId=self.worker_b.id,
                spendingDate=datetime.now().strftime("%Y-%m-%d"),
            ),
        )

        json_response = response.json
        self.assertIn("errors", json_response)

        error = json_response["errors"][0]
        if "extensions" in error and "code" in error["extensions"]:
            self.assertEqual(
                AuthorizationError.code,
                error["extensions"]["code"],
            )
        else:
            self.assertIn("authorization", error.get("message", "").lower())


class TestIDOREmployment(BaseTest):
    """Test IDOR vulnerabilities for employment-related mutations"""

    def setUp(self):
        super().setUp()
        from datetime import date

        self.company_a = CompanyFactory.create()
        self.admin_a = UserFactory.create(
            post__company=self.company_a, post__has_admin_rights=True
        )
        self.worker_a = UserFactory.create(post__company=self.company_a)

        self.company_b = CompanyFactory.create()
        self.admin_b = UserFactory.create(
            post__company=self.company_b, post__has_admin_rights=True
        )

        # Terminate worker_a's employment so it can be reattached
        self.worker_a.employments[0].end_date = date(2020, 1, 15)
        db.session.commit()

        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def test_idor_reattach_employment_cross_company_blocked(self):
        """Admin from company B cannot reattach worker from company A"""
        response = make_authenticated_request(
            time=datetime(2020, 2, 7, 6),
            submitter_id=self.admin_b.id,
            query=ApiRequests.reattach_employment,
            variables={
                "userId": self.worker_a.id,
                "companyId": self.company_a.id,
            },
        )

        self.assertIn("errors", response)
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )
