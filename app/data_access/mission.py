import graphene
from graphene.types.generic import GenericScalar

from app.helpers.controller_endpoint_utils import retrieve_max_reception_time
from app.helpers.frozen_version_utils import (
    freeze_activities,
    filter_out_future_events,
)
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models import Mission
from app.data_access.activity import ActivityOutput
from app.helpers.authentication import current_user
from app.models.comment import CommentOutput
from app.models.expenditure import ExpenditureOutput
from app.models.location_entry import LocationEntryOutput
from app.models.mission_validation import MissionValidationOutput


class MissionOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Mission
        only_fields = (
            "id",
            "reception_time",
            "name",
            "company_id",
            "company",
            "submitter_id",
            "submitter",
            "context",
            "vehicle",
            "vehicle_id",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant de la mission"
    )
    name = graphene.Field(graphene.String, description="Nom de la mission")
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )
    activities = graphene.List(
        ActivityOutput,
        description="Activités de la mission",
        include_dismissed_activities=graphene.Boolean(
            required=False,
            description="Flag pour inclure les activités effacées",
        ),
    )
    context = graphene.Field(
        GenericScalar, description="Données contextuelles libres"
    )
    company_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de l'entreprise qui effectue la mission",
    )
    submitter_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la personne qui a créé la mission",
    )
    expenditures = graphene.List(
        ExpenditureOutput,
        description="Frais associés la mission",
        include_dismissed_expenditures=graphene.Boolean(
            required=False, description="Flag pour inclure les frais effacés"
        ),
    )
    validations = graphene.List(
        MissionValidationOutput,
        description="Liste des validations de la mission",
    )
    comments = graphene.List(
        CommentOutput, description="Liste des observations de la mission"
    )
    start_location = graphene.Field(
        LocationEntryOutput, description="Lieu de début de la mission"
    )
    end_location = graphene.Field(
        LocationEntryOutput, description="Lieu de fin de la mission"
    )
    is_ended_for_self = graphene.Field(graphene.Boolean)
    deleted_at = graphene.Field(
        TimeStamp, description="Horodatage de la suppression de la mission"
    )
    is_holiday = graphene.Field(graphene.Boolean)
    deleted_by = graphene.Field(
        graphene.String,
        description="Nom de la personne ayant supprimé la mission",
    )

    def resolve_activities(self, info, include_dismissed_activities=False):
        _include_dismissed_activities = (
            True if self.is_deleted() else include_dismissed_activities
        )
        max_reception_time = retrieve_max_reception_time(info)
        if max_reception_time:
            return freeze_activities(
                self.activities,
                max_reception_time,
                _include_dismissed_activities,
            )
        return (
            self.activities
            if _include_dismissed_activities
            else self.acknowledged_activities
        )

    def resolve_expenditures(self, info, include_dismissed_expenditures=False):
        max_reception_time = retrieve_max_reception_time(info)
        if max_reception_time:
            return filter_out_future_events(
                self.expenditures, max_reception_time
            )
        return (
            self.expenditures
            if include_dismissed_expenditures
            else self.acknowledged_expenditures
        )

    def resolve_validations(self, info):
        max_reception_time = retrieve_max_reception_time(info)
        if max_reception_time:
            return filter_out_future_events(
                self.validations, max_reception_time
            )
        return self.validations

    def resolve_comments(self, info):
        max_reception_time = retrieve_max_reception_time(info)
        if max_reception_time:
            return filter_out_future_events(
                self.acknowledged_comments, max_reception_time
            )
        return self.acknowledged_comments

    def resolve_start_location(self, info):
        return self.start_location

    def resolve_end_location(self, info):
        max_reception_time = retrieve_max_reception_time(info)
        if max_reception_time:
            return self.end_location_at(max_reception_time)
        return self.end_location

    def resolve_is_ended_for_self(self, info):
        return self.ended_for(current_user)

    def resolve_deleted_at(self, info):
        return self.deleted_at()

    def resolve_is_holiday(self, info):
        return self.is_holiday()

    def resolve_deleted_by(self, info):
        return self.deleted_by()


class MissionConnection(graphene.Connection):
    class Meta:
        node = MissionOutput
