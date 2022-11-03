import graphene
from app.helpers.graphene_types import graphene_enum_type
from app.helpers.submitter_type import SubmitterType
from app.models.regulation_check import UnitType
from app.models.regulation_computation import RegulationComputation
from app.data_access.regulation_computation import RegulationComputationOutput


class Query(graphene.ObjectType):
    regulation_computation = graphene.Field(
        RegulationComputationOutput,
        user_id=graphene.Int(
            required=True,
            description="Utilisateur concerné par le calcul de dépassement de seuil",
        ),
        day=graphene.Date(
            required=True,
            description="Journée concernée par le calcul de dépassement de seuil (pour les dépassements hebdomadaires, il s'agit du lundi de la semaine) au format 'YYYY MM DD'",
        ),
        submitter_type=graphene_enum_type(SubmitterType)(
            required=True,
            description="Type d'utilisateur dont la version est utilisée pour le calcul de dépassement de seuil",
        ),
        unit=graphene_enum_type(UnitType)(
            required=False,
            description="Unité de temps d'application du seuil règlementaire",
        ),
        description="Récupération des résultats de calcul de seuils règlementaires",
    )

    def resolve_regulation_computation(
        self, info, user_id, day, submitter_type
    ):
        return RegulationComputation.query.filter(
            RegulationComputation.user_id == user_id,
            RegulationComputation.day == day,
            RegulationComputation.submitter_type == submitter_type,
        ).one_or_none()
