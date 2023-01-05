import graphene

from app.domain.permissions import only_self_employment
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.helpers.oauth.models import OAuth2Client
from app.models.employment import Employment


class OAuth2ClientOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = OAuth2Client
        only_fields = (
            "id",
            "name",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant du logiciel"
    )

    name = graphene.Field(
        graphene.String,
        required=True,
        description="Nom du logiciel",
    )


class EmploymentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Employment
        only_fields = (
            "id",
            "reception_time",
            "start_date",
            "end_date",
            "user_id",
            "user",
            "submitter_id",
            "submitter",
            "company_id",
            "company",
            "has_admin_rights",
            "email",
            "latest_invite_email_time",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant du rattachement"
    )
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )
    user_id = graphene.Field(
        graphene.Int,
        description="Identifiant de l'utilisateur concerné par le rattachement. Peut être manquant dans le cas d'une invitation par email",
    )
    submitter_id = graphene.Field(
        graphene.Int,
        description="Identifiant de la personne qui a créé le rattachement",
    )
    start_date = graphene.Field(
        graphene.String,
        required=True,
        description="Date de début du rattachement au format AAAA-MM-JJ",
    )
    end_date = graphene.Field(
        graphene.String,
        description="Date de fin du rattachement au format AAAA-MM-JJ, si présente.",
    )
    company_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de l'entreprise de rattachement",
    )
    has_admin_rights = graphene.Field(
        graphene.Boolean,
        description="Précise si le rattachement confère un accès gestionnaire ou non. Une valeur manquante équivaut à non.",
    )
    email = graphene.Field(
        graphene.String,
        description="Email éventuel vers lequel est envoyée l'invitation.",
    )

    is_acknowledged = graphene.Field(
        graphene.Boolean,
        description="Précise si le rattachement a été approuvé par l'utilisateur concerné ou s'il est en attente de validation. Un rattachement non validé ne peut pas être actif.",
    )
    latest_invite_email_time = graphene.Field(
        TimeStamp,
        required=False,
        description="Horodatage d'envoi du dernier email d'invitation",
    )
    authorized_clients = graphene.List(
        OAuth2ClientOutput,
        description="Logiciels authorisés à accéder aux données de ce rattachement",
    )

    def resolve_is_acknowledged(self, info):
        return self.is_acknowledged

    @with_authorization_policy(
        only_self_employment,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access",
    )
    def resolve_authorized_clients(self, info):
        return [
            client_id.client
            for client_id in self.client_ids
            if not client_id.is_dismissed
            and client_id.access_token is not None
        ]
