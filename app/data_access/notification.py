from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.notification import Notification


class NotificationOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Notification
        only_fields = (
            "id",
            "creation_time",
            "type",
            "read",
            "data",
        )
