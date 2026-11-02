import graphene

from app.helpers.authentication import current_user
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
    graphene_enum_type,
)
from app.models.controller_user import ControllerUser
from app.models.technical_incident import (
    TechnicalIncident,
    TechnicalIncidentNature,
    TechnicalIncidentType,
)


class TechnicalIncidentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = TechnicalIncident
        only_fields = (
            "id",
            "creation_time",
            "technical_type",
            "start_time",
            "end_time",
            "description",
        )

    technical_type = graphene.Field(
        graphene_enum_type(TechnicalIncidentType),
        description="Type de dysfonctionnement",
    )
    start_time = TimeStamp(
        required=True,
        description="Date et heure de début du dysfonctionnement",
    )
    end_time = TimeStamp(
        required=False,
        description="Date et heure de fin (absente si l'incident est en cours)",
    )
    nature = graphene.Field(
        graphene_enum_type(TechnicalIncidentNature),
        description="Nature affichée au contrôleur, dérivée du type",
    )
    is_ongoing = graphene.Boolean(
        description="Indique si l'incident est toujours en cours"
    )
    effective_end_time = TimeStamp(
        required=True,
        description="Fin effective : date de fin réelle, ou la fin plafonnée "
        "de la fenêtre de visibilité pour un incident encore en cours",
    )

    def resolve_description(self, info):
        # Champ interne réservé à l'admin/bizdev, jamais exposé aux contrôleurs.
        user = current_user
        if (
            user
            and not isinstance(user, ControllerUser)
            and (
                getattr(user, "admin", False) or getattr(user, "bizdev", False)
            )
        ):
            return self.description
        return None
