import graphene
from graphene.types.generic import GenericScalar

from app.data_access.mission import MissionOutput
from app.helpers.graphene_types import TimeStamp


class WorkDayOutput(graphene.ObjectType):
    expenditures = graphene.Field(
        GenericScalar,
        description="Liste des frais de la journée pour l'utilisateur concerné",
    )

    start_time = graphene.Field(
        TimeStamp,
        description="Horodatage de début de la journée de travail. Correspond à l'heure de début de la toute première activité",
    )
    end_time = graphene.Field(
        TimeStamp,
        description="Horodatage de fin de l'activité. Correspond à l'heure de fin de la dernière mission",
    )
    missions = graphene.List(
        MissionOutput, description="Liste des missions de la journée"
    )
    activity_timers = graphene.Field(
        GenericScalar,
        description="Décomposition de la durée de la journée par nature d'activité. La durée cumulée de chaque activité est indiquée en millisecondes.",
    )
    was_modified = graphene.Field(graphene.Boolean)
