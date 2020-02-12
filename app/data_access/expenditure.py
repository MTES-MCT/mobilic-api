from graphene_sqlalchemy import SQLAlchemyObjectType

from app.models.expenditure import Expenditure


class ExpenditureOutput(SQLAlchemyObjectType):
    class Meta:
        model = Expenditure
