import graphene

from app.helpers.authorization import with_authorization_policy, active
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.helpers.oauth import OAuth2Client


class OAuth2ClientOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = OAuth2Client
        only_fields = "id" "name"

    name = graphene.Field(graphene.String)


class Query(graphene.ObjectType):
    oauth_client_id = graphene.Field(
        OAuth2ClientOutput, client_id=graphene.Int(required=True)
    )
    Output = OAuth2ClientOutput

    @with_authorization_policy(active)
    def resolve_oauth_access_tokens(self, info, client_id):
        oauth_client = OAuth2Client.query.get(client_id)
        return oauth_client
