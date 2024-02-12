import graphene
from flask import g

from app.controllers.oauth_client import OAuth2ClientOutput
from app.domain.permissions import only_self_employment
from app.domain.user import get_user_with_hidden_email, HIDDEN_EMAIL
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.employment import Employment


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
            "team_id",
            "team",
            "hide_email",
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
    team = graphene.Field(
        lambda: TeamOutput, description="Équipe associée à ce rattachement"
    )
    should_see_certificate_info = graphene.Field(
        graphene.Boolean,
        description="Indique si l'on doit afficher les informations liées au certificat pour ce rattachement",
    )
    hide_email = graphene.Field(
        graphene.Boolean,
        description="Indique si ce salarié souhaite rendre visible son adresse email ou non",
    )

    def resolve_should_see_certificate_info(self, info):
        return self.should_see_certificate_info

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

    def resolve_email(self, info):
        if self.hide_email and self.is_acknowledged:
            return HIDDEN_EMAIL
        return self.email

    def resolve_user(self, info):
        if not self.hide_email:
            return self.user

        if self.user:
            return get_user_with_hidden_email(self.user)

    def resolve_latest_invite_email_time(self, info):
        emails = g.dataloaders["emails_in_employments"].load(self.id)

        def return_most_recent_email(emails):
            if not emails:
                return None
            return max([email_record.creation_time for email_record in emails])

        return emails.then(lambda emails: return_most_recent_email(emails))


from app.data_access.team import TeamOutput
