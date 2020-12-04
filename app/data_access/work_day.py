import graphene
from graphene.types.generic import GenericScalar

from app.data_access.mission import MissionOutput
from app.helpers.graphene_types import TimeStamp
from app.models.activity import ActivityOutput


class WorkDayOutput(graphene.ObjectType):
    user = graphene.Field(
        lambda: UserOutput,
        description="Travailleur mobile qui a réalisé la journée de travail",
    )
    user_id = graphene.Field(
        graphene.Int,
        description="Travailleur mobile qui a réalisé la journée de travail",
    )
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
        description="Horodatage de fin de la journée. Correspond à l'heure de fin de la dernière mission",
    )
    service_duration = graphene.Field(
        graphene.Int,
        description="Amplitude de la journée de travail, en secondes.",
    )
    total_work_duration = graphene.Field(
        graphene.Int,
        description="Temps de travail cumulé sur la journée, en secondes.",
    )
    activities = graphene.List(
        ActivityOutput, description="Liste des activités de la journée"
    )
    missions = graphene.List(
        MissionOutput, description="Liste des missions de la journée."
    )
    activity_durations = graphene.Field(
        GenericScalar,
        description="Temps de travail cumulés par activité, exprimés en secondes.",
    )

    def resolve_user_id(self, info):
        return self.user.id


from app.data_access.user import UserOutput
