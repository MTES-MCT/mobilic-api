from app import db, app
from app.models.notification import (
    Notification,
    create_notification,
    NotificationType,
)
from app.seed import UserFactory, CompanyFactory, EmploymentFactory
from app.tests import BaseTest, test_post_graphql
from app.tests.helpers import (
    make_authenticated_request,
    ApiRequests,
    init_regulation_checks_data,
    init_businesses_data,
)
from app.seed import AuthenticatedUserContext
from flask.ctx import AppContext
from app.domain.log_activities import log_activity
from app.models import Mission
from app.models.activity import ActivityType
from datetime import datetime, timedelta


class TestNotifications(BaseTest):
    def setUp(self):
        super().setUp()
        init_regulation_checks_data()
        init_businesses_data()
        self.company = CompanyFactory.create()
        self.admin = UserFactory.create(
            first_name="The",
            last_name="Manager",
            post__company=self.company,
            post__has_admin_rights=True,
        )
        self.worker = UserFactory.create(
            first_name="The", last_name="Employee", post__company=self.company
        )

        self._app_context = AppContext(app)
        self._app_context.__enter__()

        start_time = datetime.now() - timedelta(days=2, hours=4)
        end_time = datetime.now() - timedelta(days=2, hours=3)

        with AuthenticatedUserContext(user=self.worker):
            self.default_mission = Mission.create(
                submitter=self.worker,
                company=self.company,
                reception_time=start_time,
            )
            log_activity(
                submitter=self.worker,
                user=self.worker,
                mission=self.default_mission,
                type=ActivityType.WORK,
                switch_mode=True,
                reception_time=end_time,
                start_time=start_time,
                end_time=end_time,
            )
        db.session.commit()

        self.notification_data_map = {
            NotificationType.MISSION_AUTO_VALIDATION: {
                "mission_id": self.default_mission.id,
                "mission_start_date": self.default_mission.reception_time.strftime(
                    "%d/%m/%Y"
                ),
                "mission_name": "Test Mission",
            },
            NotificationType.MISSION_CHANGES_WARNING: {
                "mission_id": self.default_mission.id,
                "mission_start_date": self.default_mission.reception_time.strftime(
                    "%d/%m/%Y"
                ),
            },
        }

    def tearDown(self):
        self._app_context.__exit__(None, None, None)
        super().tearDown()

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

    def _get_notification_for_user_and_type(self, user_id, notif_type):
        return (
            Notification.query.filter_by(user_id=user_id, type=notif_type)
            .order_by(Notification.id.desc())
            .first()
        )

    def _create_notification(self, user, notif_type, data):
        notif = create_notification(
            user_id=user.id,
            notification_type=notif_type,
            data=data,
        )
        db.session.commit()
        return notif

    def _create_and_return_notification(self, user, notif_type):
        data = self.notification_data_map[notif_type]
        return self._create_notification(user, notif_type, data)

    def test_create_notification(self):
        notif = self._create_and_return_notification(
            self.worker, NotificationType.MISSION_CHANGES_WARNING
        )
        self.assertIsNotNone(notif.id)
        self.assertEqual(notif.user_id, self.worker.id)
        self.assertFalse(notif.read)

    def test_query_user_notifications(self):
        notif = self._create_and_return_notification(
            self.worker, NotificationType.MISSION_CHANGES_WARNING
        )
        query = """
        query GetNotifications($userId: Int!) {
            user(id: $userId) {
                notifications {
                    id
                    type
                    read
                    data
                }
            }
        }
        """
        response = test_post_graphql(
            query=query,
            mock_authentication_with_user=self.worker,
            variables={"userId": self.worker.id},
        )
        self.assertEqual(response.status_code, 200)
        notifications = response.json["data"]["user"]["notifications"]
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["id"], notif.id)
        self.assertFalse(notifications[0]["read"])

    def test_mark_notifications_as_read(self):
        notif = self._create_and_return_notification(
            self.worker, NotificationType.MISSION_CHANGES_WARNING
        )
        mutation = """
        mutation markNotificationsAsRead($notificationIds: [Int!]!) {
            account {
                markNotificationsAsRead(notificationIds: $notificationIds) {
                    id
                    read
                }
            }
        }
        """
        response = make_authenticated_request(
            time=datetime.now(),
            submitter_id=self.worker.id,
            query=mutation,
            variables={"notificationIds": [notif.id]},
            unexposed_query=True,
        )
        notif_data = response["data"]["account"]["markNotificationsAsRead"][0]
        self.assertEqual(notif_data["id"], notif.id)
        self.assertTrue(notif_data["read"])
        self.assertTrue(Notification.query.get(notif.id).read)

    def test_mission_changes_notification(self):
        self.assertIsNone(
            self._get_notification_for_user_and_type(
                self.worker.id, NotificationType.MISSION_CHANGES_WARNING
            )
        )

        self._validate_mission(
            submitter=self.worker,
            user=self.worker,
            mission=self.default_mission,
        )

        activity_end = datetime.now() - timedelta(days=2, hours=1)

        self._validate_mission(
            submitter=self.admin,
            user=self.worker,
            mission=self.default_mission,
            activity_items=[
                {
                    "edit": {
                        "activityId": self.default_mission.activities[0].id,
                        "endTime": activity_end,
                    }
                }
            ],
        )

        notif = self._get_notification_for_user_and_type(
            self.worker.id, NotificationType.MISSION_CHANGES_WARNING
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.type, NotificationType.MISSION_CHANGES_WARNING)

    def test_auto_validation_notification(self):
        from app.domain.validation import validate_mission

        self.assertIsNone(
            self._get_notification_for_user_and_type(
                self.worker.id, NotificationType.MISSION_AUTO_VALIDATION
            )
        )

        validate_mission(
            mission=self.default_mission,
            submitter=None,
            for_user=self.worker,
            is_auto_validation=True,
            is_admin_validation=False,
        )

        notification = self._get_notification_for_user_and_type(
            self.worker.id, NotificationType.MISSION_AUTO_VALIDATION
        )

        self.assertIsNotNone(notification)
        self.assertEqual(
            notification.type, NotificationType.MISSION_AUTO_VALIDATION
        )
        self.assertEqual(notification.user_id, self.worker.id)
        self.assertFalse(notification.read)

        self.assertEqual(
            notification.data["mission_id"], self.default_mission.id
        )
        self.assertIn("mission_start_date", notification.data)
        self.assertIn("mission_name", notification.data)

    def test_cant_create_notification_with_invalid_data(self):
        invalid_data = {"mission_id": self.default_mission.id}
        with self.assertRaises(ValueError) as context:
            self._create_notification(
                self.worker,
                NotificationType.MISSION_CHANGES_WARNING,
                invalid_data,
            )
        self.assertIn(
            "Missing keys in notification data", str(context.exception)
        )
