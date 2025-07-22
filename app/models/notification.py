from app import db
from app.helpers.notification_type import NotificationType
from app.models.base import BaseModel
from app.models.utils import enum_column
from app.domain.notification_data_schemas import validate_notification_data
from sqlalchemy.dialects.postgresql import JSONB


class Notification(BaseModel):
    type = enum_column(NotificationType, nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="notifications")
    read = db.Column(db.Boolean, nullable=False, default=False)
    data = db.Column(JSONB(none_as_null=True), nullable=True)


def create_notification(
    user_id: int, notification_type: NotificationType, data: dict
) -> Notification:
    """
    Create a new notification for a user.
    """
    validate_notification_data(notification_type, data)
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        data=data,
    )
    db.session.add(notification)
    return notification
