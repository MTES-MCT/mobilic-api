import graphene

from app.controllers.utils import atomic_transaction
from app.data_access.employment import OAuth2ClientOutput
from app.domain.company import link_company_to_software
from app.domain.permissions import company_admin
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import (
    with_authorization_policy,
)
from app.helpers.errors import (
    CompanyLinkNotFound,
)
from app.helpers.oauth.models import ThirdPartyClientCompany
from app.models import Company


class GenerateCompanyToken(graphene.Mutation):
    """
    Création d'un token lié au logiciel tiers et à la company
    """

    class Arguments:
        company_id = graphene.Int(required=True)
        client_id = graphene.Int(required=True)

    Output = graphene.List(OAuth2ClientOutput)

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda cls, _, info, **kwargs: kwargs[
            "company_id"
        ],
        error_message="You need to be a company admin",
    )
    def mutate(cls, _, info, company_id, client_id):
        with atomic_transaction(commit_at_end=True):
            link_company_to_software(company_id, client_id)
        company = Company.query.get(company_id)
        return company.retrieve_authorized_clients


class DismissCompanyToken(AuthenticatedMutation):
    """
    Suppression d'un token lié au logiciel tiers et à la company
    """

    class Arguments:
        client_id = graphene.Int(required=True)
        company_id = graphene.Int(required=True)

    Output = graphene.List(OAuth2ClientOutput)

    @classmethod
    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda cls, _, info, **kwargs: kwargs[
            "company_id"
        ],
        error_message="You need to be a company admin",
    )
    def mutate(cls, _, info, client_id, company_id):
        with atomic_transaction(commit_at_end=True):
            existing_link = ThirdPartyClientCompany.query.filter(
                ThirdPartyClientCompany.company_id == company_id,
                ThirdPartyClientCompany.client_id == client_id,
                ~ThirdPartyClientCompany.is_dismissed,
            ).one_or_none()
            if not existing_link:
                raise CompanyLinkNotFound

            existing_link.dismiss()
            return existing_link.company.retrieve_authorized_clients
