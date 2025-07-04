import graphene
from app.helpers.authentication import current_user, AuthenticatedMutation
from app.helpers.authorization import with_authorization_policy
from app.helpers.errors import AuthorizationError
from app.models.notification import Notification
from app.data_access.notification import NotificationOutput
from app import db


class MarkNotificationsAsRead(AuthenticatedMutation):
    class Arguments:
        notification_ids = graphene.List(graphene.Int, required=True)

    Output = graphene.List(NotificationOutput)

    @classmethod
    @with_authorization_policy(
        lambda user, *args, **kwargs: all(
            Notification.query.get(nid)
            and Notification.query.get(nid).user_id == user.id
            for nid in (kwargs.get("notification_ids") or [])
        ),
        get_target_from_args=lambda *args, **kwargs: current_user,
        error_message="Forbidden access",
    )
    def mutate(cls, _, info, notification_ids):
        notifications = Notification.query.filter(
            Notification.id.in_(notification_ids),
            Notification.user_id == current_user.id,
        ).all()
        for notification in notifications:
            if not notification.read:
                notification.read = True
        if notifications:
            db.session.commit()
        return notifications
