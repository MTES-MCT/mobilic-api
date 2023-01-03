import graphene
from sqlalchemy import desc

from app.domain.permissions import only_self
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.helpers.oauth import OAuth2Token, OAuth2Client
from app.models import User


class OAuth2TokenOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = OAuth2Token
        only_fields = "token"

    client_name = graphene.Field(graphene.String)

    def resolve_client_name(self, info):
        client = OAuth2Client.query.get(self.client_id)
        return client.name


class Query(graphene.ObjectType):
    oauth_access_tokens = graphene.List(
        OAuth2TokenOutput, user_id=graphene.Int(required=True)
    )
    Output = OAuth2TokenOutput

    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda *args, **kwargs: User.query.get(
            kwargs["user_id"]
        ),
        error_message="Forbidden access",
    )
    def resolve_oauth_access_tokens(self, info, user_id):
        tokens = (
            OAuth2Token.query.filter(
                OAuth2Token.user_id == user_id,
                OAuth2Token.revoked_at.is_(None),
            )
            .order_by(desc(OAuth2Token.creation_time))
            .all()
        )
        return tokens
