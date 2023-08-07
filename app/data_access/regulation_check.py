import json

import graphene

from app.data_access.regulatory_alert import RegulatoryAlertOutput
from app.domain.regulations_per_day import NATINF_32083
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


def get_alert_sanction(alert):
    if alert is None or alert.extra is None:
        return None
    extra = json.loads(alert.extra)
    if "sanction_code" not in extra:
        return None
    return extra.get("sanction_code")


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

    alert = graphene.Field(
        RegulatoryAlertOutput,
        description="Alerte remontée par ce calcul",
    )

    def resolve_label(self, info):
        sanction = get_alert_sanction(self.alert)
        if not sanction:
            return self.label

        if sanction == NATINF_32083:
            return self.label.replace("quotidien", "de nuit")
        return self.label

    def resolve_description(self, info):
        sanction = get_alert_sanction(self.alert)
        if not sanction:
            return self.description

        if sanction == NATINF_32083:
            return f"{self.description}. Si une partie du travail de la journée s'effectue entre minuit et 5 heures, la durée maximale du travail est réduite à 10 heures"
        return self.description
