import graphene

from app.models.event import EventBaseValidationStatus
from app.models.expenditure import Expenditure, ExpenditureTypes
from app.helpers.graphene_types import (
    graphene_enum_type,
    BaseSQLAlchemyObjectType,
)


class ExpenditureOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Expenditure

    type = graphene_enum_type(ExpenditureTypes)()
    team = graphene.List(graphene.Int)
    validation_status = graphene_enum_type(EventBaseValidationStatus)()
