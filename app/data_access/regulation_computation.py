import graphene
from app.data_access.regulatory_alert import RegulatoryAlertOutput
from app.data_access.user import UserOutput
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.helpers.submitter_type import SubmitterType
from app.models.regulation_check import RegulationCheck, UnitType
from app.models.regulation_computation import RegulationComputation
from app.models.regulatory_alert import RegulatoryAlert


class RegulationComputationOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = RegulationComputation

    day = graphene.Field(
        graphene.Date,
        required=True,
        description="Journée concernée par le calcul de dépassement de seuil (pour les dépassements hebdomadaires, il s'agit du lundi de la semaine)",
    )

    user = graphene.Field(
        UserOutput,
        description="Utilisateur concerné par le calcul de dépassement de seuil",
    )

    submitter_type = graphene_enum_type(SubmitterType)(
        required=True,
        description="Type d'utilisateur dont la version est utilisée pour le calcul de dépassement de seuil",
    )

    alerts = graphene.List(
        RegulatoryAlertOutput,
        description="Liste des alertes remontées par ce calcul",
        unit=graphene_enum_type(UnitType)(
            required=False,
            description="Unité de temps de ces seuils règlementaires",
        ),
    )

    def resolve_alerts(self, info, unit=None):
        base_query = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id == self.user.id,
            RegulatoryAlert.day == self.day,
            RegulatoryAlert.submitter_type == self.submitter_type,
        )

        if unit:
            base_query = base_query.filter(
                RegulatoryAlert.regulation_check.has(
                    RegulationCheck.unit == unit
                )
            )
        return base_query.all()
