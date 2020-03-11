import graphene

from app.models.event import DismissType
from app.models.expenditure import Expenditure, ExpenditureType
from app.helpers.graphene_types import (
    graphene_enum_type,
    BaseSQLAlchemyObjectType,
)


class ExpenditureOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Expenditure

    type = graphene_enum_type(ExpenditureType)()
    team = graphene.List(graphene.Int)
    dismiss_type = graphene_enum_type(DismissType)(required=False)
