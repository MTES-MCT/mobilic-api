import graphene
from flask import g

from app.data_access.user import UserOutput
from app.models import UserReadToken
from app.models.user_read_token import UserReadTokenOutput


class UserReadOutput(graphene.ObjectType):
    user = graphene.Field(UserOutput)
    token_info = graphene.Field(UserReadTokenOutput)


class Query(graphene.ObjectType):
    user_from_read_token = graphene.Field(
        UserReadOutput,
        token=graphene.String(required=True),
        description="Consultation des informations d'un utilisateur à partir d'un jeton de lecture",
    )

    def resolve_user_from_read_token(self, info, token):
        existing_token = UserReadToken.get_token(token)
        user = existing_token.user
        g.user = user
        info.context.max_activity_date = existing_token.creation_day
        info.context.min_activity_date = existing_token.history_start_day
        return UserReadOutput(user=user, token_info=existing_token)
