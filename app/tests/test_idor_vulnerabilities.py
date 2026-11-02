"""
Test suite for IDOR (Insecure Direct Object Reference) vulnerabilities
"""

import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from unittest import TestCase, expectedFailure

from flask.ctx import AppContext

import config
from app import app, db
from app.domain.log_activities import log_activity
from app.helpers.errors import AuthorizationError
from app.helpers.submitter_type import SubmitterType
from app.models import (
    Employment,
    Mission,
    RegulationComputation,
    ScenarioTesting,
    Team,
)
from app.models.activity import ActivityType, Activity
from app.seed import ControllerUserFactory, UserFactory, CompanyFactory
from app.seed.factories import ControllerControlFactory
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

    def test_admin_regulation_computations_requires_company_admin(self):
        db.session.add(
            RegulationComputation(
                day=date(2025, 5, 10),
                submitter_type=SubmitterType.ADMIN,
                user_id=self.worker_a.id,
            )
        )
        db.session.commit()

        query = """
            query ($id: Int!) {
                company(id: $id) {
                    adminRegulationComputationsByUserAndByDay {
                        day
                        userId
                    }
                }
            }
        """

        worker_response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_a.id,
            query=query,
            variables=dict(id=self.company_a.id),
        )
        self.assertIn("errors", worker_response)
        self.assertEqual(
            AuthorizationError.code,
            worker_response["errors"][0]["extensions"]["code"],
        )

        admin_response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_a.id,
            query=query,
            variables=dict(id=self.company_a.id),
        )
        self.assertNotIn("errors", admin_response)
        returned_user_ids = [
            row["userId"]
            for row in admin_response["data"]["company"][
                "adminRegulationComputationsByUserAndByDay"
            ]
        ]
        self.assertIn(self.worker_a.id, returned_user_ids)

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


REPO_ROOT = os.path.dirname(config.__file__)

ADD_SCENARIO_TESTING_RESULT = """
    mutation ($userId: Int!, $scenario: ScenarioEnum!, $action: ActionEnum!) {
        addScenarioTestingResult(userId: $userId, scenario: $scenario, action: $action) {
            success
        }
    }
"""


class TestScenarioTestingIdor(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.attacker = UserFactory.create(post__company=self.company)
        self.victim = UserFactory.create(post__company=self.company)

    @expectedFailure
    def test_cannot_add_scenario_testing_result_for_another_user(self):
        """AE1 [High] IDOR addScenarioTestingResult: A must not write a result owned by B."""
        make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.attacker.id,
            query=ADD_SCENARIO_TESTING_RESULT,
            variables={
                "user_id": self.victim.id,
                "scenario": "Certificate banner",
                "action": "Load",
            },
            unexposed_query=True,
        )
        self.assertEqual(
            ScenarioTesting.query.filter_by(user_id=self.victim.id).count(),
            0,
            "An authenticated user was able to create a ScenarioTesting "
            "record attributed to another user (IDOR)",
        )


class TestOW4MissionControlExportIDOR(BaseTest):
    def setUp(self):
        super().setUp()
        self.controller = ControllerUserFactory.create()
        self.controlled_user = UserFactory.create()
        self.control = ControllerControlFactory.create(
            user_id=self.controlled_user.id,
            controller_id=self.controller.id,
        )

        self.other_company = CompanyFactory.create()
        self.other_worker = UserFactory.create(
            post__company=self.other_company
        )

        self._app_context = AppContext(app)
        self._app_context.__enter__()

        now = datetime.now()
        with AuthenticatedUserContext(user=self.other_worker):
            self.foreign_mission = Mission.create(
                submitter=self.other_worker,
                company=self.other_company,
                reception_time=now,
            )
            log_activity(
                submitter=self.other_worker,
                user=self.other_worker,
                mission=self.foreign_mission,
                type=ActivityType.WORK,
                switch_mode=False,
                reception_time=now,
                start_time=now - timedelta(hours=2),
                end_time=now - timedelta(hours=1),
            )
        db.session.commit()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    @expectedFailure
    def test_mission_must_belong_to_control(self):
        """mission_id never checked against control_id."""
        with app.test_client(
            mock_authentication_with_user=self.controller
        ) as client, app.app_context():
            response = client.post(
                "/users/generate_mission_control_export",
                json={
                    "mission_id": self.foreign_mission.id,
                    "control_id": self.control.id,
                },
            )

        self.assertEqual(
            response.status_code,
            403,
            "A controller obtained a PDF for a mission outside their control",
        )


class TestOW7BindEmploymentToTeamCrossTenant(BaseTest):
    change_employee_team_by_employment = """
        mutation changeEmployeeTeam(
            $companyId: Int!
            $employmentId: Int
            $teamId: Int
        ) {
            employments {
                changeEmployeeTeam(
                    companyId: $companyId
                    employmentId: $employmentId
                    teamId: $teamId
                ) {
                    id
                }
            }
        }
    """

    def setUp(self):
        super().setUp()
        self.company_a = CompanyFactory.create()
        self.admin_a = UserFactory.create(
            post__company=self.company_a, post__has_admin_rights=True
        )

        self.company_b = CompanyFactory.create()
        self.worker_b = UserFactory.create(post__company=self.company_b)
        self.employment_b = self.worker_b.employments[0]
        self.original_team_id = self.employment_b.team_id

        self._app_context = AppContext(app)
        self._app_context.__enter__()

        self.team_a = Team(name="Team A", company_id=self.company_a.id)
        db.session.add(self.team_a)
        db.session.commit()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    @expectedFailure
    def test_admin_cannot_bind_foreign_employment(self):
        """_bind_employment_to_team ignores company_id."""
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin_a.id,
            query=self.change_employee_team_by_employment,
            variables=dict(
                companyId=self.company_a.id,
                employmentId=self.employment_b.id,
                teamId=self.team_a.id,
            ),
        )

        employment_b = Employment.query.get(self.employment_b.id)
        self.assertEqual(
            employment_b.team_id,
            self.original_team_id,
            "An admin reassigned an employment belonging to another company",
        )
        self.assertIn("errors", response)


class TestOW11HashIdSecretDefault(TestCase):
    @expectedFailure
    def test_no_weak_hash_id_secret_fallback(self):
        """HASH_ID_SECRET defaults to 'secret' (config.py:111)."""
        env = dict(os.environ)
        env.pop("HASH_ID_SECRET", None)
        env.pop("DOTENV_FILE", None)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import config; print(repr(config.Config.HASH_ID_SECRET))",
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(
            "'secret'",
            result.stdout,
            "HASH_ID_SECRET falls back to the guessable value 'secret'",
        )
