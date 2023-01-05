import graphene

from app.controllers.utils import atomic_transaction
from app.domain.oauth_token import (
    get_active_oauth_token_for_user,
    revoke_oauth_token,
)
from app.domain.permissions import only_self
from app.helpers.authentication import AuthenticatedMutation
from app.helpers.authorization import with_authorization_policy
from app.helpers.errors import BadRequestError, InvalidParamsError
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.helpers.oauth import OAuth2Token, OAuth2Client, get_or_create_token
from app.models import User


class OAuth2TokenOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = OAuth2Token
        only_fields = ("token", "id", "client_id")

    client_name = graphene.Field(graphene.String)

    def resolve_client_name(self, info):
        client = OAuth2Client.query.get(self.client_id)
        return client.name


class Query(graphene.ObjectType):
    oauth_access_tokens = graphene.List(
        OAuth2TokenOutput, user_id=graphene.Int(required=True)
    )

    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda *args, **kwargs: kwargs["user_id"],
        error_message="Forbidden access",
    )
    def resolve_oauth_access_tokens(self, info, user_id):
        return get_active_oauth_token_for_user(user_id)


class CreateOauthToken(AuthenticatedMutation):
    """
    Création d'un token pour un user et un client_id

    Retourne la liste des tokens existants pour le user
    """

    class Arguments:
        user_id = graphene.Int(required=True)
        client_id = graphene.Int(required=True)

    Output = graphene.List(OAuth2TokenOutput)

    @classmethod
    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda *args, **kwargs: kwargs["user_id"],
        error_message="Forbidden access",
    )
    def mutate(cls, _, info, user_id, client_id):
        client = OAuth2Client.query.get(client_id)
        user = User.query.get(user_id)
        if not client or not user:
            raise BadRequestError()
        get_or_create_token(client, "", user)
        return get_active_oauth_token_for_user(user_id)


class RevokeOauthToken(AuthenticatedMutation):
    """
    Revocation d'un token pour un user et un client_id

    Retourne la liste des tokens existants pour le user associé au token supprimé
    """

    class Arguments:
        token_id = graphene.Int(required=True)

    Output = graphene.List(OAuth2TokenOutput)

    @classmethod
    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda *args, **kwargs: OAuth2Token.query.get(
            kwargs["token_id"]
        ).user,
        error_message="Forbidden access",
    )
    def mutate(cls, _, info, token_id):
        with atomic_transaction(commit_at_end=True):
            existing_token = OAuth2Token.query.get(token_id)
            if not existing_token or existing_token.revoked:
                raise InvalidParamsError("Forbidden access")
            revoke_oauth_token(existing_token)
        return get_active_oauth_token_for_user(existing_token.user_id)
