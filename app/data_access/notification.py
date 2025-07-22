from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.notification import Notification
from app.helpers.graphene_types import TimeStamp


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

    creation_time = TimeStamp(
        description="Date de création de la notification'."
    )
