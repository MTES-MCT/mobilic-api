import graphene

from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import ControllerUser


class ControllerUserOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ControllerUser
        only_fields = (
            "id",
            "first_name",
            "last_name",
            "email",
        )

    id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant Mobilic du contrôleur",
    )
    first_name = graphene.Field(
        graphene.String, required=True, description="Prénom"
    )
    last_name = graphene.Field(
        graphene.String, required=True, description="Nom"
    )
    email = graphene.Field(
        graphene.String,
        required=False,
        description="Adresse email",
    )
