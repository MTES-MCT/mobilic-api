import graphene

from app.data_access.control_data import ControllerControlOutput
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
        from_date=graphene.Date(
            required=False, description="Date de début de l'historique"
        ),
        to_date=graphene.Date(
            required=False, description="Date de fin de l'historique"
        ),
        controls_type=graphene.Argument(
            graphene.String, description="Type de contrôles souhaités"
        ),
    )

    def resolve_controls(
        self, info, from_date=None, to_date=None, controls_type=None
    ):
        from app.models.queries import query_controls

        return query_controls(
            controller_user_id=self.id,
            start_time=from_date,
            end_time=to_date,
            controls_type=controls_type,
        ).all()
