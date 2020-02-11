import graphene
from graphene.types.generic import GenericScalar

from app.data_access.activity import ActivityOutput
from app.data_access.expenditure import ExpenditureOutput
from app.helpers import DateTimeWithTimeStampSerialization


class WorkDayOutput(graphene.ObjectType):
    activities = graphene.List(ActivityOutput)
    expenditures = graphene.List(ExpenditureOutput)

    start_time = graphene.Field(DateTimeWithTimeStampSerialization)
    end_time = graphene.Field(DateTimeWithTimeStampSerialization)
    vehicle_registration_number = graphene.Field(graphene.String)
    mission = graphene.Field(graphene.String)
    activity_timers = graphene.Field(GenericScalar)
