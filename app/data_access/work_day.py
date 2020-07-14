import graphene
from graphene.types.generic import GenericScalar

from app.data_access.mission import MissionOutput
from app.helpers.graphene_types import TimeStamp


class WorkDayOutput(graphene.ObjectType):
    expenditures = graphene.Field(GenericScalar)

    start_time = graphene.Field(TimeStamp)
    end_time = graphene.Field(TimeStamp)
    missions = graphene.List(MissionOutput)
    activity_timers = graphene.Field(GenericScalar)
    was_modified = graphene.Field(graphene.Boolean)
