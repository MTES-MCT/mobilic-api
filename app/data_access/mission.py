import graphene
from graphene.types.generic import GenericScalar

from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models import Mission
from app.models.activity import ActivityOutput
from app.models.address import BaseAddressOutput
from app.models.comment import CommentOutput
from app.models.expenditure import ExpenditureOutput
from app.models.location_entry import LocationEntryType
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
        ActivityOutput, description="Activités de la mission"
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
        ExpenditureOutput, description="Frais associés la mission"
    )
    validations = graphene.List(
        MissionValidationOutput,
        description="Liste des validations de la mission",
    )
    comments = graphene.List(
        CommentOutput, description="Liste des commentaires de la mission"
    )
    start_location = graphene.Field(
        BaseAddressOutput, description="Lieu de début de la mission"
    )
    end_location = graphene.Field(
        BaseAddressOutput, description="Lieu de fin de la mission"
    )

    def resolve_activities(self, info):
        return self.acknowledged_activities

    def resolve_expenditures(self, info):
        return self.acknowledged_expenditures

    def resolve_validations(self, info):
        return self.latest_validations_per_user

    def resolve_comments(self, info):
        return self.acknowledged_comments

    def resolve_start_location(self, info):
        return self.start_location

    def resolve_end_location(self, info):
        return self.end_location
