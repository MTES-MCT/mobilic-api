from graphene_sqlalchemy import SQLAlchemyObjectType

from app.models.activity import Activity


class ActivityOutput(SQLAlchemyObjectType):
    class Meta:
        model = Activity
