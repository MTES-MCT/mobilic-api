import graphene
from graphene.types.generic import GenericScalar

from app.data_access.mission import MissionOutput
from app.helpers.graphene_types import TimeStamp
from app.models import Mission
from app.models.activity import ActivityOutput, Activity
from app.models.queries import query_activities


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
    mission_names = graphene.List(
        graphene.String, description="Liste des noms de mission de la journée"
    )
    activity_durations = graphene.Field(
        GenericScalar,
        description="Temps de travail cumulés par activité, exprimés en secondes.",
    )
    activities = graphene.List(
        ActivityOutput, description="Activités de la journée"
    )
    missions = graphene.List(
        MissionOutput, description="Missions de la journée"
    )

    def resolve_user_id(self, info):
        return self.user.id

    def resolve_activities(self, info):
        return query_activities(
            include_dismissed_activities=False,
            start_time=self.start_time,
            end_time=self.end_time,
            user_id=self.user.id,
        ).all()

    def resolve_missions(self, info):
        activity_query = query_activities(
            include_dismissed_activities=False,
            start_time=self.start_time,
            end_time=self.end_time,
            user_id=self.user.id,
        )
        mission_ids = (
            activity_query.with_entities(Activity.mission_id).distinct().all()
        )
        return Mission.query.filter(Mission.id.in_(mission_ids)).all()


class WorkDayConnection(graphene.Connection):
    class Meta:
        node = WorkDayOutput


from app.data_access.user import UserOutput
