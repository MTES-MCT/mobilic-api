import graphene
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.regulation_check import (
    RegulationCheck,
    RegulationCheckType,
    RegulationRule,
    UnitType,
)


class RegulationCheckOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = RegulationCheck
        only_fields = (
            "type",
            "label",
            "description",
            "regulation_rule",
            "unit",
        )

    type = graphene_enum_type(RegulationCheckType)(
        required=True,
        description="Identifiant de la règle d'un seuil règlementaire",
    )

    label = graphene.Field(
        graphene.String,
        required=True,
        description="Nom de la règle du seuil règlementaire",
    )

    description = graphene.Field(
        graphene.String,
        required=True,
        description="Description de la règle du seuil règlementaire",
    )

    regulation_rule = graphene_enum_type(RegulationRule)(
        required=True, description="Seuil règlementaire"
    )

    unit = graphene_enum_type(UnitType)(
        required=True,
        description="Unité de temps d'application de ce seuil règlementaire",
    )
