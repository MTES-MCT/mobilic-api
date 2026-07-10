from datetime import datetime, timedelta

from app import app, db
from app.domain.log_activities import log_activity
from app.helpers.errors import AuthorizationError, InvalidParamsError
from app.models import Mission
from app.models.activity import ActivityType, Activity
from app.models.mission_validation import MissionValidation
from app.seed import UserFactory, CompanyFactory
from app.tests import (
    BaseTest,
    AuthenticatedUserContext,
)
from app.tests.helpers import make_authenticated_request, ApiRequests


class TestPermissionActivities(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.another_admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        self.worker = UserFactory.create(post__company=self.company)
        with app.app_context():
            with AuthenticatedUserContext(user=self.worker):
                self.mission_by_worker = Mission.create(
                    submitter=self.worker,
                    company=self.company,
                    reception_time=datetime.now(),
                )
                self.activity_by_worker = log_activity(
                    submitter=self.worker,
                    user=self.worker,
                    mission=self.mission_by_worker,
                    type=ActivityType.WORK,
                    switch_mode=True,
                    reception_time=datetime.now(),
                    start_time=datetime(2022, 1, 1, 1),
                    end_time=datetime(2022, 1, 1, 2),
                )
            db.session.commit()

            with AuthenticatedUserContext(user=self.admin):
                self.mission_by_admin = Mission.create(
                    submitter=self.admin,
                    company=self.company,
                    reception_time=datetime.now(),
                )
                self.activity_by_admin = log_activity(
                    submitter=self.admin,
                    user=self.worker,
                    mission=self.mission_by_admin,
                    type=ActivityType.WORK,
                    switch_mode=True,
                    reception_time=datetime.now(),
                    start_time=datetime(2022, 2, 1, 1),
                    end_time=datetime(2022, 2, 1, 2),
                )

                log_activity(
                    submitter=self.admin,
                    user=self.worker,
                    mission=self.mission_by_worker,
                    type=ActivityType.WORK,
                    switch_mode=True,
                    reception_time=datetime.now(),
                    start_time=datetime(2022, 1, 2, 1),
                    end_time=datetime(2022, 1, 2, 2),
                )
            db.session.flush()
            db.session.commit()

    def tearDown(self):
        super().tearDown()

    def test_worker_can_dismiss_its_activity(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker.id,
            query=ApiRequests.cancel_activity,
            variables=dict(
                activity_id=self.activity_by_worker.id,
            ),
        )
        self.assertTrue(
            response["data"]["activities"]["cancelActivity"]["success"]
        )
        self.assertEqual(
            self.worker.id,
            Activity.query.get(self.activity_by_worker.id).dismiss_author.id,
        )

    def test_worker_can_edit_its_activity(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activity_id=self.activity_by_worker.id,
                end_time=datetime(2022, 1, 1, 3),
            ),
        )
        self.assertEqual(
            self.activity_by_worker.id,
            response["data"]["activities"]["editActivity"]["id"],
        )
        self.assertTrue(
            datetime(2022, 1, 1, 3),
            Activity.query.get(self.activity_by_worker.id).end_time,
        )

    def test_admin_cannot_dismiss_worker_activity(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.cancel_activity,
            variables=dict(
                activity_id=self.activity_by_worker.id,
            ),
        )
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )
        self.assertIsNone(
            Activity.query.get(self.activity_by_worker.id).dismiss_author
        )

    def test_admin_cannot_edit_worker_activity(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activity_id=self.activity_by_worker.id,
                end_time=datetime(2022, 1, 1, 3),
            ),
        )
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )
        self.assertTrue(
            datetime(2022, 1, 1, 2),
            Activity.query.get(self.activity_by_worker.id).end_time,
        )

    def test_admin_can_dismiss_an_activity_he_created(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.cancel_activity,
            variables=dict(
                activity_id=self.activity_by_admin.id,
            ),
        )
        self.assertTrue(
            response["data"]["activities"]["cancelActivity"]["success"]
        )
        self.assertEqual(
            self.admin.id,
            Activity.query.get(self.activity_by_admin.id).dismiss_author.id,
        )

    def test_admin_can_edit_an_activity_he_created(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.edit_activity,
            variables=dict(
                activity_id=self.activity_by_admin.id,
                end_time=datetime(2022, 2, 1, 3),
            ),
        )
        self.assertEqual(
            self.activity_by_admin.id,
            response["data"]["activities"]["editActivity"]["id"],
        )
        self.assertTrue(
            datetime(2022, 2, 1, 3),
            Activity.query.get(self.activity_by_admin.id).end_time,
        )

    def test_admin_can_log_in_a_mission_he_created(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.log_activity,
            variables=dict(
                type=ActivityType.DRIVE,
                start_time=datetime(2022, 2, 2, 1),
                mission_id=self.mission_by_admin.id,
                user_id=self.worker.id,
            ),
        )
        self.assertIsNotNone(
            response["data"]["activities"]["logActivity"]["id"]
        )

    def test_admin_cannot_log_in_a_mission_he_did_not_created(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.admin.id,
            query=ApiRequests.log_activity,
            variables=dict(
                type=ActivityType.DRIVE,
                start_time=datetime(2022, 1, 3, 1),
                end_time=datetime(2022, 1, 3, 2),
                switch=False,
                mission_id=self.mission_by_worker.id,
                user_id=self.worker.id,
            ),
        )
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )


class TestDisputeActivities(BaseTest):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory.create()
        admin = UserFactory.create(
            post__company=self.company, post__has_admin_rights=True
        )
        worker = UserFactory.create(post__company=self.company)
        another_worker = UserFactory.create(
            post__company=self.company
        )
        self.admin_id = admin.id
        self.worker_id = worker.id
        self.another_worker_id = another_worker.id
        with app.app_context():
            with AuthenticatedUserContext(user=worker):
                mission = Mission.create(
                    submitter=worker,
                    company=self.company,
                    reception_time=datetime.now(),
                )
                activity = log_activity(
                    submitter=worker,
                    user=worker,
                    mission=mission,
                    type=ActivityType.WORK,
                    switch_mode=True,
                    reception_time=datetime.now(),
                    start_time=datetime.now() - timedelta(hours=4),
                    end_time=datetime.now() - timedelta(hours=1),
                )
            self.mission_id = mission.id
            self.activity_id = activity.id
            db.session.commit()

            worker_validation = MissionValidation(
                submitter=worker,
                mission=mission,
                user_id=worker.id,
                is_admin=False,
                reception_time=datetime.now(),
            )
            admin_validation = MissionValidation(
                submitter=admin,
                mission=mission,
                user_id=worker.id,
                is_admin=True,
                reception_time=datetime.now(),
            )
            db.session.add(worker_validation)
            db.session.add(admin_validation)
            db.session.commit()

    def test_worker_can_dispute_activity(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_id,
            query=ApiRequests.dispute_activity,
            variables=dict(
                activity_id=self.activity_id,
                text="Horaires incorrects",
            ),
        )
        dispute = response["data"]["activities"]["disputeActivity"][
            "dispute"
        ]
        self.assertEqual("created", dispute["status"])
        self.assertEqual("Horaires incorrects", dispute["text"])
        db_activity = Activity.query.get(self.activity_id)
        self.assertEqual("created", db_activity.dispute["status"])

    def test_another_worker_cannot_dispute_activity(self):
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.another_worker_id,
            query=ApiRequests.dispute_activity,
            variables=dict(
                activity_id=self.activity_id,
                text="Horaires incorrects",
            ),
        )
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_double_dispute_refused(self):
        make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_id,
            query=ApiRequests.dispute_activity,
            variables=dict(
                activity_id=self.activity_id,
                text="Première contestation",
            ),
        )
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_id,
            query=ApiRequests.dispute_activity,
            variables=dict(
                activity_id=self.activity_id,
                text="Deuxième contestation",
            ),
        )
        self.assertEqual(
            InvalidParamsError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_dispute_expired_after_15_days(self):
        with app.app_context():
            admin_validation = MissionValidation.query.filter(
                MissionValidation.mission_id == self.mission_id,
                MissionValidation.is_admin.is_(True),
            ).first()
            admin_validation.reception_time = (
                datetime.now() - timedelta(days=16)
            )
            db.session.commit()

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_id,
            query=ApiRequests.dispute_activity,
            variables=dict(
                activity_id=self.activity_id,
                text="Contestation tardive",
            ),
        )
        self.assertEqual(
            InvalidParamsError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_dispute_without_admin_validation(self):
        with app.app_context():
            MissionValidation.query.filter(
                MissionValidation.mission_id == self.mission_id,
                MissionValidation.is_admin.is_(True),
            ).delete()
            db.session.commit()

        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_id,
            query=ApiRequests.dispute_activity,
            variables=dict(
                activity_id=self.activity_id,
                text="Contestation sans validation",
            ),
        )
        self.assertEqual(
            InvalidParamsError.code,
            response["errors"][0]["extensions"]["code"],
        )

    def test_cancel_dispute_by_submitter(self):
        make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_id,
            query=ApiRequests.dispute_activity,
            variables=dict(
                activity_id=self.activity_id,
                text="Contestation à annuler",
            ),
        )
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_id,
            query=ApiRequests.cancel_dispute,
            variables=dict(activity_id=self.activity_id),
        )
        dispute = response["data"]["activities"]["cancelDispute"][
            "dispute"
        ]
        self.assertEqual("cancelled", dispute["status"])
        db_activity = Activity.query.get(self.activity_id)
        self.assertEqual("cancelled", db_activity.dispute["status"])

    def test_another_worker_cannot_cancel_dispute(self):
        make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker_id,
            query=ApiRequests.dispute_activity,
            variables=dict(
                activity_id=self.activity_id,
                text="Contestation",
            ),
        )
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.another_worker_id,
            query=ApiRequests.cancel_dispute,
            variables=dict(activity_id=self.activity_id),
        )
        self.assertEqual(
            AuthorizationError.code,
            response["errors"][0]["extensions"]["code"],
        )
