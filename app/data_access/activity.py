import graphene
from flask import g
from graphene.types.generic import GenericScalar

from app.helpers.controller_endpoint_utils import retrieve_max_reception_time
from app.helpers.frozen_version_utils import (
    filter_out_future_events,
)
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
    graphene_enum_type,
)
from app.models import Activity, ActivityVersion
from app.models.activity import ActivityType


class ActivityVersionOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ActivityVersion
        only_fields = (
            "id",
            "reception_time",
            "start_time",
            "end_time",
            "context",
            "submitter_id",
            "submitter",
        )
        description = "Version d'une activité. Chaque mise à jour de l'heure de début ou de fin d'une activité donne lieu à une nouvelle version"

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant de la version"
    )
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )
    start_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de début de l'activité pour cette version",
    )
    end_time = graphene.Field(
        TimeStamp,
        required=False,
        description="Horodatage de fin de l'activité pour cette version",
    )
    submitter_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la personne qui a enregistré cette version (auteur de la mise à jour)",
    )


class ActivityOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Activity
        only_fields = (
            "id",
            "reception_time",
            "mission_id",
            "mission",
            "start_time",
            "end_time",
            "last_update_time",
            "dismissed_at",
            "dismiss_author_id",
            "dismiss_author",
            "type",
            "context",
            "user_id",
            "user",
            "submitter_id",
            "submitter",
            "last_submitter_id",
        )
        description = "Activité dans la journée de travail"

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant de l'activité"
    )
    mission_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la mission dans laquelle s'inscrit l'activité",
    )
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )
    start_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de début de l'activité",
    )
    end_time = graphene.Field(
        TimeStamp,
        required=False,
        description="Horodatage de fin de l'activité",
    )
    last_update_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de la dernière mise à jour de l'activité",
    )
    user_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant du travailleur mobile qui a effectué l'activité",
    )
    dismissed_at = graphene.Field(
        TimeStamp,
        description="Horodatage de suppression de l'activité, si jamais l'activité a été effacée",
    )
    dismiss_author_id = graphene.Field(
        graphene.Int,
        description="Identifiant de la personne qui a effacé l'activité, si jamais l'activité a été effacée",
    )
    context = graphene.Field(
        GenericScalar, description="Données contextuelles libres"
    )
    submitter_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la personne qui a enregistré l'activité",
    )
    type = graphene_enum_type(ActivityType)(
        required=True, description="Nature de l'activité"
    )
    versions = graphene.List(
        ActivityVersionOutput,
        description="Historique des versions de l'activité.",
    )
    last_submitter_id = graphene.Field(
        graphene.Int,
        description="Identifiant de la personne qui a effectué la dernière modification sur l'activité",
    )

    def resolve_versions(self, info):
        max_reception_time = retrieve_max_reception_time(info)
        if max_reception_time:
            return filter_out_future_events(self.versions, max_reception_time)
        return self.versions

    def resolve_user(self, info):
        if not self.user_id:
            return None
        return g.dataloaders["users"].load(self.user_id)


class ActivityConnection(graphene.Connection):
    class Meta:
        node = ActivityOutput
