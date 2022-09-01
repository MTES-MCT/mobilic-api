import graphene

from app.data_access.control_data import ControllerControlOutput
from app.domain.permissions import user_resolver_with_consultation_scope
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
    controls = graphene.Field(
        graphene.List(ControllerControlOutput),
        description="Liste des contrôles réalisés par le contrôleur",
    )

    @user_resolver_with_consultation_scope(
        error_message="Forbidden access to field 'controls' of controller_user object. The field is only accessible to the controller_user himself."
    )
    def resolve_controls(self, info, consultation_scope):
        return self.query_controls()
