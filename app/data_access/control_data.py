import graphene

from app.data_access.mission import MissionOutput
from app.data_access.regulation_computation import (
    RegulationComputationByUnitOutput,
)
from app.domain.regulation_computations import get_regulation_computations
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
    graphene_enum_type,
)
from app.helpers.submitter_type import SubmitterType
from app.models.controller_control import ControllerControl
from app.models.employment import EmploymentOutput
from app.models.regulation_check import UnitType


class ControllerControlOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ControllerControl

    qr_code_generation_time = graphene.Field(TimeStamp, required=True)
    creation_time = graphene.Field(TimeStamp, required=True)
    nb_controlled_days = graphene.Field(
        graphene.Int,
        required=False,
        description="Nombre de jours de travail sur lesquels porte le contrôle",
    )

    employments = graphene.List(
        EmploymentOutput,
        description="Liste des rattachements actifs au moment du contrôle",
    )

    missions = graphene.List(
        MissionOutput,
        mission_id=graphene.Int(
            required=False,
            description="Filtre sur une mission à l'aide de son identifiant",
        ),
        include_dismissed_activities=graphene.Boolean(
            required=False,
            description="Flag pour inclure les activités effacées",
        ),
        description="Liste des missions de l'utilisateur pendant la période de contrôle.",
    )

    history_start_date = graphene.Field(
        graphene.Date,
        required=True,
        description="Date de début de l'historique pouvant être contrôlé",
    )

    regulation_computations_by_unit = graphene.List(
        RegulationComputationByUnitOutput,
        submitter_type=graphene_enum_type(SubmitterType)(
            required=False,
            description="Version utilisée pour le calcul des dépassements de seuil",
        ),
        unit=graphene_enum_type(UnitType)(
            required=False,
            description="Unité de temps pour le groupement des seuils règlementaires",
        ),
        description="Résultats de calcul de seuils règlementaires groupés par jour ou par semaine",
    )

    def resolve_employments(
        self,
        info,
    ):
        employments = sorted(
            self.user.active_employments_between(
                self.history_start_date,
                self.history_end_date,
                include_pending_ones=False,
            ),
            key=lambda e: e.start_date,
            reverse=True,
        )
        return employments

    def resolve_missions(self, info, mission_id=None):
        missions, has_next_page = self.user.query_missions_with_limit(
            start_time=self.history_start_date,
            end_time=self.history_end_date,
            limit_fetch_activities=2000,
            max_reception_time=self.qr_code_generation_time,
            mission_id=mission_id,
            include_dismissed_activities=True,
        )
        return missions

    def resolve_history_start_date(self, info):
        return self.history_start_date

    def resolve_regulation_computations_by_unit(
        self, info, unit=UnitType.DAY, submitter_type=None
    ):
        regulation_computations_by_unit = get_regulation_computations(
            user_id=self.user.id,
            start_date=self.history_start_date,
            end_date=self.history_end_date,
            submitter_type=submitter_type,
            grouped_by_unit=unit,
        )
        return [
            RegulationComputationByUnitOutput(
                day=day_, regulation_computations=computations_
            )
            for day_, computations_ in regulation_computations_by_unit.items()
        ]
