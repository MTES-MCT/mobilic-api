import graphene
from app.data_access.regulatory_alert import RegulatoryAlertOutput
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.helpers.submitter_type import SubmitterType
from app.models.regulation_check import (
    RegulationCheck,
    RegulationCheckType,
    RegulationRule,
    UnitType,
)
from app.models.regulatory_alert import RegulatoryAlert


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

    alerts = graphene.List(
        RegulatoryAlertOutput,
        description="Liste des alertes associées à ce seuil règlementaire",
        user_id=graphene.Int(
            required=True,
            description="Identifiant de l'utilisateur concernée par le calcul de dépassement de seuil",
        ),
        day=graphene.Date(
            required=True,
            description="Journée concernée par le calcul de dépassement de seuil (pour les dépassements hebdomadaires, il s'agit du lundi de la semaine)",
        ),
        submitter_type=graphene_enum_type(SubmitterType)(
            required=True,
            description="Type d'utilisateur dont la version est utilisée pour le calcul de dépassement de seuil",
        ),
    )

    def resolve_alerts(self, info, user_id, day, submitter_type):
        return RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id == user_id,
            RegulatoryAlert.day == day,
            RegulatoryAlert.submitter_type == submitter_type,
            RegulatoryAlert.regulation_check.has(
                RegulationCheck.type == self.type
            ),
        ).all()
