import graphene
from app.data_access.regulation_check import RegulationCheckOutput
from app.data_access.user import UserOutput
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.helpers.submitter_type import SubmitterType
from app.models.regulation_check import RegulationCheck, UnitType
from app.models.regulation_computation import RegulationComputation


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

    checks = graphene.Field(
        graphene.List(RegulationCheckOutput),
        description="Liste des calculs de dépassement de seuil",
        unit=graphene_enum_type(UnitType)(
            required=False,
            description="Unité de temps d'application de ce seuil règlementaire",
        ),
    )

    def resolve_checks(self, info, unit=None):
        base_query = RegulationCheck.query
        if unit:
            base_query = base_query.filter(RegulationCheck.unit == unit)
        return base_query.all()
