import graphene
from app.data_access.regulation_check import RegulationCheckOutput
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.regulatory_alert import RegulatoryAlert
from graphene.types.generic import GenericScalar


class RegulatoryAlertOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = RegulatoryAlert
        only_fields = (
            "extra",
            "regulation_check",
        )

    extra = GenericScalar(
        required=False,
        description="Un dictionnaire de données additionnelles.",
    )

    regulation_check = graphene.Field(
        RegulationCheckOutput,
        description="Dépassement de seuil franchi",
    )
