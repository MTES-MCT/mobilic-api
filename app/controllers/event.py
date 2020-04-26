import graphene

from app.helpers.graphene_types import DateTimeWithTimeStampSerialization


class EventInput:
    event_time = graphene.Argument(
        DateTimeWithTimeStampSerialization, required=True
    )
