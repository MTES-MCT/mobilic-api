import graphene

from app.helpers.graphene_types import (
    graphene_enum_type,
    BaseSQLAlchemyObjectType,
)
from app.models.activity import (
    Activity,
    ActivityTypes,
    ActivityValidationStatus,
)


class ActivityOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Activity

    type = graphene_enum_type(ActivityTypes)()
    team = graphene.List(graphene.Int)
    validation_status = graphene_enum_type(ActivityValidationStatus)()
