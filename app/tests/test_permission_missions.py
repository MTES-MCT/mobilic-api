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
)


class TestPermissionMissions(BaseTest):
    def setUp(self):
        super().setUp()
        init_regulation_checks_data()

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

    def _create_mission(self, submitter, user, start_time, end_time):
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
                reception_time=end_time,
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

    def _validate_mission(self, submitter, user, mission):
        return make_authenticated_request(
            time=datetime.now(),
            submitter_id=submitter.id,
            query=ApiRequests.validate_mission,
            variables=dict(
                missionId=mission.id,
                usersIds=[user.id],
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
