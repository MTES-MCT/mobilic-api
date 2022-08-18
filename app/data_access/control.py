import graphene

from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.controller_control import ControllerControl


class ControllerControlOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ControllerControl

    qr_code_generation_time = graphene.Field(TimeStamp, required=True)
