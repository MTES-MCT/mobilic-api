from graphene_sqlalchemy import SQLAlchemyObjectType
import graphene

from app.helpers.graphene_types import graphene_enum_type
from app.models.activity import Activity, ActivityTypes


class TeamMateOutput(graphene.ObjectType):
    id = graphene.Int()


class ActivityOutput(SQLAlchemyObjectType):
    class Meta:
        model = Activity

    type = graphene_enum_type(ActivityTypes)()
    team = graphene.List(graphene.Int)
