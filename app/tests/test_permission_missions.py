from datetime import datetime, timedelta

from flask.ctx import AppContext


from app import app, db
from app.domain.log_activities import log_activity
from app.helpers.errors import MissionNotAlreadyValidatedByUserError
from app.models import Mission
from app.models.activity import ActivityType
from app.seed import UserFactory, CompanyFactory
from app.tests import (
    BaseTest,
    AuthenticatedUserContext,
)
from app.tests.helpers import (
    init_regulation_checks_data,
    make_authenticated_request,
    ApiRequests,
    init_businesses_data,
)


class TestPermissionMissions(BaseTest):
    def setUp(self):
        super().setUp()
        init_regulation_checks_data()
        init_businesses_data()

        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)
        self.another_worker = UserFactory.create(post__company=self.company)

        self._app_context = AppContext(app)
        self._app_context.__enter__()

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

    def _create_mission(
        self, submitter, user, start_time, end_time, reception_time=None
    ):
        with AuthenticatedUserContext(user=submitter):
            mission = Mission.create(
                submitter=submitter,
                company=self.company,
                reception_time=start_time,
            )
            log_activity(
                submitter=submitter,
                user=user,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=reception_time if reception_time else end_time,
                start_time=start_time,
                end_time=end_time,
            )
        db.session.commit()

        return mission

    def _add_activity_to_mission(
        self, submitter, user, start_time, end_time, mission
    ):
        with AuthenticatedUserContext(user=submitter):
            log_activity(
                submitter=submitter,
                user=user,
                mission=mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=end_time,
                start_time=start_time,
                end_time=end_time,
            )
        db.session.commit()

    def _validate_mission(self, submitter, user, mission, activity_items=[]):
        return make_authenticated_request(
            time=datetime.now(),
            submitter_id=submitter.id,
            query=ApiRequests.validate_mission,
            variables=dict(
                missionId=mission.id,
                usersIds=[user.id],
                activityItems=activity_items,
            ),
        )

    def test_admin_can_validate_mission_validated_by_employee(self):
        mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(hours=4),
            end_time=datetime.now() - timedelta(hours=1),
        )

        self._validate_mission(
            submitter=self.worker, user=self.worker, mission=mission
        )

        response = self._validate_mission(
            submitter=self.admin, user=self.worker, mission=mission
        )

        if "errors" in response:
            self.fail(f"Validate mission returned an error: {response}")

    def test_admin_cannot_validate_mission_not_validated_by_employee(self):
        mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(hours=4),
            end_time=datetime.now() - timedelta(hours=1),
        )

        response = self._validate_mission(
            submitter=self.admin, user=self.worker, mission=mission
        )

        self.assertEqual(
            MissionNotAlreadyValidatedByUserError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_admin_can_validate_mission_not_validated_by_employee_if_mission_has_more_than_10_days(
        self,
    ):
        # Si une mission court depuis plus de dix jours sans que le salarié ne l'ait validée,
        # j'obtiens alors les droits pour y apporter des modifications et la valider

        mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(days=11),
            end_time=datetime.now() - timedelta(days=11) + timedelta(hours=1),
        )

        response = self._validate_mission(
            submitter=self.admin, user=self.worker, mission=mission
        )

        if "errors" in response:
            self.fail(f"Validate mission returned an error: {response}")

    def test_admin_can_validate_mission_not_validated_by_employee_if_last_activity_has_more_than_24_hours(
        self,
    ):
        # Si la dernière activité court depuis plus de 24 heures,
        # j'obtiens alors les droits pour y apporter des modifications et la valider

        mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(hours=25),
            end_time=None,
            reception_time=datetime.now(),
        )

        new_end_time = datetime.now() - timedelta(hours=2)
        response = self._validate_mission(
            submitter=self.admin,
            user=self.worker,
            mission=mission,
            activity_items=[
                {
                    "edit": {
                        "activityId": mission.activities[0].id,
                        "endTime": new_end_time,
                    }
                }
            ],
        )

        if "errors" in response:
            self.fail(f"Validate mission returned an error: {response}")

    def test_admin_can_not_validate_mission_not_validated_by_employee_if_last_activity_has_more_than_24_hours_but_has_end_time(
        self,
    ):
        mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(hours=25),
            end_time=datetime.now() - timedelta(hours=2),
            reception_time=datetime.now(),
        )

        response = self._validate_mission(
            submitter=self.admin, user=self.worker, mission=mission
        )

        if "errors" not in response:
            self.fail(f"Admin should not be able to validate")

    def test_admin_can_validate_mission_old_enough_even_if_updating_start_date_case_24h(
        self,
    ):
        # A mission has last activity started more than 24h ago
        # Admin can validate in this special case
        mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(hours=25),
            end_time=None,
            reception_time=datetime.now(),
        )

        # Admin will validate while modifying start time of activity
        new_start_time = datetime.now() - timedelta(hours=19)
        new_end_time = datetime.now() - timedelta(hours=1)
        response = self._validate_mission(
            submitter=self.admin,
            user=self.worker,
            mission=mission,
            activity_items=[
                {
                    "edit": {
                        "activityId": mission.activities[0].id,
                        "startTime": new_start_time,
                    }
                },
                {
                    "edit": {
                        "activityId": mission.activities[0].id,
                        "endTime": new_end_time,
                    }
                },
            ],
        )

        if "errors" in response:
            self.fail(f"Validate mission returned an error: {response}")

    def test_admin_can_validate_mission_old_enough_even_if_updating_start_date_case_10d(
        self,
    ):
        # A mission has last activity started more than 24h ago
        # Admin can validate in this special case
        mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(days=11),
            end_time=datetime.now() - timedelta(days=9) + timedelta(hours=8),
        )

        # Admin will validate while modifying start time of activity
        new_start_time = (
            datetime.now() - timedelta(days=9) + timedelta(hours=2)
        )
        response = self._validate_mission(
            submitter=self.admin,
            user=self.worker,
            mission=mission,
            activity_items=[
                {
                    "edit": {
                        "activityId": mission.activities[0].id,
                        "startTime": new_start_time,
                    }
                }
            ],
        )

        if "errors" in response:
            self.fail(f"Validate mission returned an error: {response}")

    def test_admin_can_validate_mission_not_validated_by_all_employees_with_team_mode(
        self,
    ):
        # Dans le cas des missions de groupe, j'effectue la validation par salarié et non pas par mission.
        # Si certains membres du groupe n'ont pas encore validé la mission en question,
        # je peux tout de même valider le temps de travail de ceux qui l'ont déjà fait

        mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(hours=4),
            end_time=datetime.now() - timedelta(hours=1),
        )

        self._add_activity_to_mission(
            submitter=self.worker,
            user=self.another_worker,
            start_time=datetime.now() - timedelta(hours=4),
            end_time=datetime.now() - timedelta(hours=1),
            mission=mission,
        )

        self._validate_mission(
            submitter=self.another_worker,
            user=self.another_worker,
            mission=mission,
        )

        response = self._validate_mission(
            submitter=self.admin, user=self.another_worker, mission=mission
        )

        if "errors" in response:
            self.fail(f"Validate mission returned an error: {response}")

        response = self._validate_mission(
            submitter=self.admin, user=self.worker, mission=mission
        )

        self.assertEqual(
            MissionNotAlreadyValidatedByUserError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_admin_can_validate_mission_not_validated_by_employee_if_added_by_admin(
        self,
    ):
        # Si je saisis une mission passée pour le compte d'un salarié, en tant que gestionnaire.
        # Le salarié sera notifié mais sa validation ne sera pas demandée

        mission = self._create_mission(
            submitter=self.admin,
            user=self.worker,
            start_time=datetime.now() - timedelta(hours=4),
            end_time=datetime.now() - timedelta(hours=1),
        )

        response = self._validate_mission(
            submitter=self.admin, user=self.worker, mission=mission
        )

        if "errors" in response:
            self.fail(f"Validate mission returned an error: {response}")

    def test_admin_can_validate_own_mission(self):

        mission = self._create_mission(
            submitter=self.admin,
            user=self.admin,
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now(),
        )

        response = self._validate_mission(
            submitter=self.admin, user=self.admin, mission=mission
        )

        if "errors" in response:
            self.fail(
                f"Validation of own mission by admin returned an error: {response}"
            )

    def test_admin_can_validate_team_mission_for_himself(
        self,
    ):
        # Dans le cas des missions de groupe, en tant que gestionnaire je peux valider ma mission qui a été crée par un autre salarié

        mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(hours=4),
            end_time=datetime.now() - timedelta(hours=1),
        )

        self._add_activity_to_mission(
            submitter=self.worker,
            user=self.admin,
            start_time=datetime.now() - timedelta(hours=4),
            end_time=datetime.now() - timedelta(hours=1),
            mission=mission,
        )

        response = self._validate_mission(
            submitter=self.admin,
            user=self.admin,
            mission=mission,
        )

        if "errors" in response:
            self.fail(f"Validate mission returned an error: {response}")
