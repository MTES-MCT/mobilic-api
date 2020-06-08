import graphene

from app.helpers.graphene_types import DateTimeWithTimeStampSerialization


class EventInput:
    event_time = graphene.Argument(
        DateTimeWithTimeStampSerialization,
        required=True,
        description="Horodatage de l'évènement. Dans un fonctionnement idéal sans mode offline la valeur devrait être très proche de l'horodatage de réception de l'évènement par le serveur",
    )
