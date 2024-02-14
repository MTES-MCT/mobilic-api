import graphene
from flask import g
from graphene.types.generic import GenericScalar

from app.domain.mission import get_start_location, get_end_location
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
        expenditures = g.dataloaders["expenditures_in_missions"].load(self.id)

        def process_expenditures(expenditures):
            if max_reception_time:
                return filter_out_future_events(
                    expenditures, max_reception_time
                )
            return (
                expenditures
                if include_dismissed_expenditures
                else sorted(
                    [e for e in expenditures if not e.is_dismissed],
                    key=lambda e: e.reception_time,
                )
            )

        return expenditures.then(
            lambda expenditures: process_expenditures(expenditures)
        )

    def resolve_validations(self, info):
        max_reception_time = retrieve_max_reception_time(info)

        def process_validations(validations):
            if max_reception_time:
                return filter_out_future_events(
                    validations, max_reception_time
                )
            return validations

        validations = g.dataloaders["validations_in_missions"].load(self.id)
        return validations.then(
            lambda validations: process_validations(validations)
        )

    def resolve_comments(self, info):
        max_reception_time = retrieve_max_reception_time(info)
        comments = g.dataloaders["comments_in_missions"].load(self.id)

        def process_comments(comments):
            acknowledged_comments = sorted(
                [c for c in comments if not c.is_dismissed],
                key=lambda c: c.reception_time,
            )
            if max_reception_time:
                return filter_out_future_events(
                    acknowledged_comments, max_reception_time
                )
            return acknowledged_comments

        return comments.then(lambda comments: process_comments(comments))

    def resolve_start_location(self, info):
        location_entries = g.dataloaders["location_entries_in_missions"].load(
            self.id
        )
        return location_entries.then(
            lambda entries: get_start_location(entries)
        )

    def resolve_end_location(self, info):
        max_reception_time = retrieve_max_reception_time(info)
        location_entries = g.dataloaders["location_entries_in_missions"].load(
            self.id
        )

        def process_location_entries(entries):
            if max_reception_time:
                entries = filter_out_future_events(entries, max_reception_time)
            return get_end_location(entries)

        return location_entries.then(
            lambda entries: process_location_entries(entries)
        )

    def resolve_is_ended_for_self(self, info):
        return self.ended_for(current_user)

    def resolve_deleted_at(self, info):
        return self.deleted_at()

    def resolve_deleted_by(self, info):
        return self.deleted_by()

    def resolve_vehicle(self, info):
        if not self.vehicle_id:
            return None

        return g.dataloaders["vehicles"].load(self.vehicle_id)


class MissionConnection(graphene.Connection):
    class Meta:
        node = MissionOutput
