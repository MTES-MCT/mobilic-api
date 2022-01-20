import graphene
from graphene.types.generic import GenericScalar

from app.data_access.mission import MissionOutput
from app.helpers.graphene_types import TimeStamp
from app.data_access.activity import ActivityOutput


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

    day = graphene.Field(graphene.Date, description="Date du jour de travail")

    start_time = graphene.Field(
        TimeStamp,
        description="Horodatage de début de la journée de travail. Correspond à l'heure de début de la toute première activité",
    )
    last_activity_start_time = graphene.Field(
        TimeStamp,
        description="Horodatage de début de la dernière activité de la journée.",
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
    mission_names = GenericScalar(
        description="Noms et identifiants des mission de la journée"
    )
    activity_durations = graphene.Field(
        GenericScalar,
        description="Temps de travail cumulés par activité, exprimés en secondes.",
    )

    def resolve_user_id(self, info):
        return self.user.id


class WorkDayConnection(graphene.Connection):
    class Meta:
        node = WorkDayOutput


from app.data_access.user import UserOutput
