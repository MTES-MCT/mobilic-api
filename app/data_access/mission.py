import graphene
from graphene.types.generic import GenericScalar

from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.helpers.authentication import current_user
from app.models import Mission
from app.models.activity import ActivityOutput
from app.models.expenditure import ExpenditureOutput


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
    validated = graphene.Field(
        graphene.Boolean,
        description="Précise si la mission a été validée par l'utilisateur (requêté)",
    )

    def resolve_activities(self, info):
        return self.acknowledged_activities

    def resolve_expenditures(self, info):
        return self.acknowledged_expenditures

    def resolve_validated(self, info):
        user = getattr(info.context, "user_being_queried", current_user)
        return self.validated_by(user)
