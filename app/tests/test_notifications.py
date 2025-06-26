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

        self.default_mission = self._create_mission(
            submitter=self.worker,
            user=self.worker,
            start_time=datetime.now() - timedelta(days=2, hours=4),
            end_time=datetime.now() - timedelta(days=2, hours=3),
        )

        self.notificationData = {
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
        db.session.refresh(mission)
        return mission

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

    def test_create_notification(self):
        notif = create_notification(
            user_id=self.worker.id,
            notification_type=NotificationType.MISSION_CHANGES_WARNING,
            data=self.notificationData[
                NotificationType.MISSION_CHANGES_WARNING
            ],
        )
        db.session.commit()
        db.session.refresh(notif)
        self.assertIsNotNone(notif.id)
        self.assertEqual(notif.user_id, self.worker.id)
        self.assertFalse(notif.read)

    def test_query_user_notifications(self):
        notif = create_notification(
            user_id=self.worker.id,
            notification_type=NotificationType.MISSION_CHANGES_WARNING,
            data=self.notificationData[
                NotificationType.MISSION_CHANGES_WARNING
            ],
        )
        db.session.commit()

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
        notif = create_notification(
            user_id=self.worker.id,
            notification_type=NotificationType.MISSION_CHANGES_WARNING,
            data=self.notificationData[
                NotificationType.MISSION_CHANGES_WARNING
            ],
        )
        db.session.commit()

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
        notif = (
            Notification.query.filter_by(
                user_id=self.worker.id,
                type=NotificationType.MISSION_CHANGES_WARNING,
            )
            .order_by(Notification.id.desc())
            .first()
        )
        self.assertIsNone(notif)

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

        notif = (
            Notification.query.filter_by(
                user_id=self.worker.id,
                type=NotificationType.MISSION_CHANGES_WARNING,
            )
            .order_by(Notification.id.desc())
            .first()
        )
        self.assertIsNotNone(notif)
        self.assertEqual(notif.type, NotificationType.MISSION_CHANGES_WARNING)

    def test_cant_create_notification_with_invalid_data(self):
        invalid_data = {"mission_id": self.default_mission.id}
        with self.assertRaises(ValueError) as context:
            create_notification(
                user_id=self.worker.id,
                notification_type=NotificationType.MISSION_CHANGES_WARNING,
                data=invalid_data,
            )
        self.assertIn(
            "Missing keys in notification data", str(context.exception)
        )
