import graphene
from flask import g

from app.data_access.regulation_check import RegulationCheckOutput
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.helpers.submitter_type import SubmitterType
from app.models import RegulatoryAlert
from app.models.regulation_check import RegulationCheck, UnitType
from app.models.regulation_computation import RegulationComputation


def get_or_cache_regulation_checks():
    if not hasattr(g, "regulation_checks"):
        g.regulation_checks = RegulationCheck.query.all()
    return g.regulation_checks


def get_regulation_checks_by_unit(unit):
    regulation_checks = get_or_cache_regulation_checks()
    if unit:
        regulation_checks = [rc for rc in regulation_checks if rc.unit == unit]
    return regulation_checks


def get_regulation_check_by_type(type):
    regulation_checks = get_or_cache_regulation_checks()
    for rc in regulation_checks:
        if rc.type == type:
            return rc
    return None


class RegulationComputationOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = RegulationComputation

    day = graphene.Field(
        graphene.Date,
        required=True,
        description="Journée concernée par le calcul de dépassement de seuil (pour les dépassements hebdomadaires, il s'agit du lundi de la semaine)",
    )

    user_id = graphene.Field(
        graphene.Int,
        description="Identifiant de l'utilisateur concerné par le calcul de dépassement de seuil",
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
        regulation_checks = get_regulation_checks_by_unit(unit=unit)

        if not regulation_checks:
            return None

        regulatory_alerts = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id == self.user.id,
            RegulatoryAlert.day == self.day,
            RegulatoryAlert.submitter_type == self.submitter_type,
        )
        regulation_checks_extended = []

        current_employments = self.user.active_employments_at(self.day)
        current_employment = (
            current_employments[0] if len(current_employments) > 0 else None
        )

        for regulation_check in regulation_checks:
            regulatory_alert = regulatory_alerts.filter(
                RegulatoryAlert.regulation_check_id == regulation_check.id
            ).one_or_none()
            setattr(regulation_check, "alert", regulatory_alert)
            if current_employment:
                setattr(
                    regulation_check, "business", current_employment.business
                )
            regulation_checks_extended.append(regulation_check)

        return regulation_checks_extended


class RegulationComputationByDayOutput(graphene.ObjectType):
    def __init__(self, day, regulation_computations):
        self.day = day
        self.regulation_computations = regulation_computations

    day = graphene.Field(
        graphene.Date,
        description="Journée pour laquelle les seuils sont calculés (pour les calculs hebdomadaires, il s'agit du premier jour de la semaine en considérant qu'elle commence le lundi)",
    )

    regulation_computations = graphene.List(
        RegulationComputationOutput,
        description="Liste des résultats de calcul de seuils règlementaires pour ce jour",
    )

    def __repr__(self):
        return f"Day {self.day} - #{len(self.regulation_computations)}"
