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
        RegulationCheckOutput,
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
            setattr(regulation_check, "alert", regulatory_alert)
            regulation_checks_extended.append(regulation_check)

        return regulation_checks_extended


class RegulationComputationByDayOutput(graphene.ObjectType):
    def __init__(self, day, regulation_computations):
        self.day = day
        self.regulation_computations = regulation_computations

    day = graphene.Field(
        graphene.Date,
        description="Journée du groupe",
    )

    regulation_computations = graphene.List(
        RegulationComputationOutput,
        description="Liste des résultats de calcul de seuils règlementaires pour ce jour",
    )

    def __repr__(self):
        return f"Day {self.day} - #{len(self.regulation_computations)}"
