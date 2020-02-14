from graphene_sqlalchemy import SQLAlchemyObjectType
import graphene

from app.models.expenditure import Expenditure, ExpenditureTypes
from app.helpers.graphene_types import graphene_enum_type


class ExpenditureOutput(SQLAlchemyObjectType):
    class Meta:
        model = Expenditure

    type = graphene_enum_type(ExpenditureTypes)()
    team = graphene.List(graphene.Int)
