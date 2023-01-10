import graphene

from app.helpers.authorization import with_authorization_policy, active
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.helpers.oauth import OAuth2Client


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


class Query(graphene.ObjectType):
    oauth_client = graphene.Field(
        OAuth2ClientOutput, client_id=graphene.Int(required=True)
    )
    Output = OAuth2ClientOutput

    @with_authorization_policy(active)
    def resolve_oauth_client(self, info, client_id):
        oauth_client = OAuth2Client.query.get(client_id)
        return oauth_client
