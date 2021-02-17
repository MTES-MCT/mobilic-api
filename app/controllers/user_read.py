import graphene
from flask import g

from app.data_access.user import UserOutput
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated_and_active,
    current_user,
)
from app.models import UserReadToken


class GenerateReadTokenMutation(graphene.Mutation):
    """
    Génération d'un jeton d'accès en lecture seule pour contrôle.

    """

    token = graphene.String(required=True)

    @classmethod
    @with_authorization_policy(authenticated_and_active)
    def mutate(cls, _, info):
        token = UserReadToken.get_or_create(current_user)
        return GenerateReadTokenMutation(token=token.token)


class Query(graphene.ObjectType):
    user_from_read_token = graphene.Field(
        UserOutput,
        token=graphene.String(required=True),
        description="Consultation des informations d'un utilisateur à partir d'un jeton de lecture",
    )

    def resolve_user_from_read_token(self, info, token):
        existing_token = UserReadToken.get_token(token)
        user = existing_token.user
        g.user = user
        return user
