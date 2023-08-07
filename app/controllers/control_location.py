import graphene

from app.domain.control_location import find_control_location_by_department
from app.helpers.authorization import (
    controller_only,
    with_authorization_policy,
)
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import ControlLocation


class ControlLocationOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ControlLocation
        only_fields = (
            "id",
            "department",
            "commune",
            "label",
        )


class Query(graphene.ObjectType):

    control_location = graphene.List(
        ControlLocationOutput, department=graphene.String(required=True)
    )

    @classmethod
    @with_authorization_policy(controller_only)
    def resolve_control_location(self, _, info, department):
        return find_control_location_by_department(department)
