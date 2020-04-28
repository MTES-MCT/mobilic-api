import graphene
from graphene.types.generic import GenericScalar

from app.helpers.graphene_types import DateTimeWithTimeStampSerialization
from app.models.mission import MissionOutput
from app.models.vehicle import VehicleOutput


class WorkDayOutput(graphene.ObjectType):
    expenditures = graphene.Field(GenericScalar)

    start_time = graphene.Field(DateTimeWithTimeStampSerialization)
    end_time = graphene.Field(DateTimeWithTimeStampSerialization)
    vehicles = graphene.List(VehicleOutput)
    missions = graphene.List(MissionOutput)
    activity_timers = graphene.Field(GenericScalar)
    was_modified = graphene.Field(graphene.Boolean)
