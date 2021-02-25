import graphene
from flask import g

from app.data_access.user import UserOutput
from app.models import UserReadToken


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
