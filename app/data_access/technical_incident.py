import graphene

from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
    graphene_enum_type,
)
from app.models.technical_incident import (
    TechnicalIncident,
    TechnicalIncidentCategory,
    TechnicalIncidentNature,
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

    start_time = TimeStamp(
        required=True,
        description="Date et heure de début du dysfonctionnement",
    )
    end_time = TimeStamp(
        required=False,
        description="Date et heure de fin (absente si l'incident est en cours)",
    )
    category = graphene.Field(
        graphene_enum_type(TechnicalIncidentCategory),
        description="Catégorie technique, dérivée du type",
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
        description="Fin effective : date de fin réelle, ou fin forcée à "
        "start + 24h pour un incident en cours",
    )
    has_forced_end = graphene.Boolean(
        description="Incident en cours dont la fin a été forcée après 24h"
    )
