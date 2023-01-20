import graphene

from app.controllers.utils import Void, atomic_transaction
from app.domain.employment import validate_employment
from app.domain.permissions import only_self_employment
from app.domain.third_party_employment import (
    generate_employment_token,
    fetch_third_party_employment_link,
)
from app.domain.user import activate_user
from app.helpers.api_key_authentication import (
    check_protected_client_id,
    check_protected_client_id_company_id,
)
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import (
    active,
    with_authorization_policy,
    with_protected_authorization_policy,
)
from app.helpers.errors import (
    EmploymentLinkNotFound,
    AuthenticationError,
)
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.helpers.oauth.models import ThirdPartyClientEmployment


class ThirdPartyClientEmploymentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ThirdPartyClientEmployment
        only_fields = (
            "employment_id",
            "client_id",
            "access_token",
            "employment",
        )

    client_name = graphene.String()

    def resolve_client_name(self, info):
        return self.client.name


class GenerateEmploymentToken(graphene.Mutation):
    """
    Création d'un token lié au logiciel tiers et à l'employment
    """

    class Arguments:
        employment_id = graphene.Int(required=True)
        client_id = graphene.Int(required=True)
        invitation_token = graphene.String(required=True)

    Output = Void

    @classmethod
    def mutate(cls, _, info, employment_id, client_id, invitation_token):
        with atomic_transaction(commit_at_end=True):
            existing_link = fetch_third_party_employment_link(
                client_id, employment_id, invitation_token
            )

            generate_employment_token(existing_link)
            activate_user(existing_link.employment.user)
            validate_employment(existing_link.employment)

            return Void(success=True)


class DismissEmploymentToken(AuthenticatedMutation):
    """
    Suppression d'un token lié au logiciel tiers et à l'employment
    """

    class Arguments:
        employment_id = graphene.Int(required=True)
        client_id = graphene.Int(required=True)

    Output = Void

    @classmethod
    @with_authorization_policy(active)
    @with_authorization_policy(
        only_self_employment,
        get_target_from_args=lambda *args, **kwargs: kwargs["employment_id"],
        error_message="Forbidden access",
    )
    def mutate(cls, _, info, employment_id, client_id):
        with atomic_transaction(commit_at_end=True):
            existing_link = ThirdPartyClientEmployment.query.filter(
                ThirdPartyClientEmployment.employment_id == employment_id,
                ThirdPartyClientEmployment.client_id == client_id,
                ~ThirdPartyClientEmployment.is_dismissed,
            ).one_or_none()

            if not existing_link:
                raise EmploymentLinkNotFound

            existing_link.dismiss()
            return Void(success=True)


class Query(graphene.ObjectType):

    employment_token = graphene.Field(
        ThirdPartyClientEmploymentOutput,
        client_id=graphene.Int(required=True),
        employment_id=graphene.Int(required=True),
        description="Données sur le lien d'accès entre le salarié et le logiciel",
    )

    @classmethod
    @with_protected_authorization_policy(
        authorization_rule=check_protected_client_id,
        get_target_from_args=lambda *args, **kwargs: kwargs["client_id"],
        error_message="You do not have access to the provided client id",
    )
    def resolve_employment_token(self, info, _, client_id, employment_id):
        client_employment_link = ThirdPartyClientEmployment.query.filter(
            ThirdPartyClientEmployment.employment_id == employment_id,
            ThirdPartyClientEmployment.client_id == client_id,
            ~ThirdPartyClientEmployment.is_dismissed,
        ).one_or_none()

        if (
            client_employment_link
            and not check_protected_client_id_company_id(
                client_employment_link.employment.company_id
            )
        ):
            raise AuthenticationError("Company token has been revoked")

        return client_employment_link


class PrivateQuery(graphene.ObjectType):

    client_employment_link = graphene.Field(
        ThirdPartyClientEmploymentOutput,
        client_id=graphene.Int(required=True),
        employment_id=graphene.Int(required=True),
        invitation_token=graphene.String(required=True),
    )

    @classmethod
    def resolve_client_employment_link(
        self, info, _, client_id, employment_id, invitation_token
    ):
        client_employment_link = fetch_third_party_employment_link(
            client_id, employment_id, invitation_token
        )

        return client_employment_link
