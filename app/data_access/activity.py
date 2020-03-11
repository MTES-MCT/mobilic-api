import graphene

from app.helpers.graphene_types import (
    graphene_enum_type,
    BaseSQLAlchemyObjectType,
)
from app.models.activity import Activity, ActivityType, ActivityDismissType


class ActivityOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Activity

    type = graphene_enum_type(ActivityType)()
    team = graphene.List(graphene.Int)
    dismiss_type = graphene_enum_type(ActivityDismissType)(required=False)
