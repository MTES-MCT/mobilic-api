import graphene
from graphene.types.generic import GenericScalar

from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.notification_campaign import NotificationCampaign
from app.models import User


class NotificationCampaignOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = NotificationCampaign
        only_fields = (
            "id",
            "creation_time",
            "title",
            "body",
            "target_type",
            "status",
            "targeted_count",
            "total_recipients",
            "sent_count",
            "failed_count",
            "clicked_count",
            "scheduled_at",
            "completed_at",
        )

    target_users = graphene.List(GenericScalar)

    def resolve_target_users(self, info):
        if not self.target_user_ids:
            return None
        users = User.query.filter(
            User.id.in_(self.target_user_ids)
        ).all()
        return [
            {
                "id": u.id,
                "firstName": u.first_name,
                "lastName": u.last_name,
                "email": u.email,
            }
            for u in users
        ]

    creation_time = TimeStamp(
        description="Date de création de la campagne"
    )
    scheduled_at = TimeStamp(
        description="Date d'envoi programmé"
    )
    completed_at = TimeStamp(
        description="Date de fin d'envoi"
    )
