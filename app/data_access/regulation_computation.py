import graphene
from app.data_access.regulation_check import RegulationCheckOutput
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


class RegulationCheckExtendedOutput(graphene.ObjectType):
    def __init__(self, regulation_check, alert):
        self.regulation_check = regulation_check
        self.alert = alert

    regulation_check = graphene.Field(
        RegulationCheckOutput,
        description="Liste des seuils calculés",
    )
    alert = graphene.Field(
        RegulatoryAlertOutput,
        description="Liste des alertes remontées par ce calcul",
    )


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

    regulation_checks = graphene.List(
        RegulationCheckExtendedOutput,
        description="Liste des seuils règlementaires calculés",
        unit=graphene_enum_type(UnitType)(
            required=False,
            description="Unité de temps de ces seuils règlementaires",
        ),
    )

    def resolve_regulation_checks(self, info, unit=None):
        base_query = RegulationCheck.query
        if unit:
            base_query = base_query.filter(RegulationCheck.unit == unit)
        regulation_checks = base_query.all()

        if not regulation_checks:
            return None

        regulatory_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id == self.user.id,
            RegulatoryAlert.day == self.day,
            RegulatoryAlert.submitter_type == self.submitter_type,
        )

        regulation_checks_extended = []
        for regulation_check in regulation_checks:
            regulatory_alert = regulatory_alerts.filter(
                RegulatoryAlert.regulation_check_id == regulation_check.id
            ).one_or_none()
            regulation_checks_extended.append(
                RegulationCheckExtendedOutput(
                    regulation_check, regulatory_alert
                )
            )

        return regulation_checks_extended
