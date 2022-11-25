from itertools import groupby

import graphene
from sqlalchemy import func

from app.data_access.mission import MissionOutput
from app.data_access.regulation_computation import (
    RegulationComputationByDayOutput,
    RegulationComputationByWeekOutput,
)
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
    graphene_enum_type,
)
from app.helpers.submitter_type import SubmitterType
from app.models.controller_control import ControllerControl
from app.models.employment import EmploymentOutput
from app.models.regulation_computation import RegulationComputation


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

    regulation_computations_by_day = graphene.List(
        RegulationComputationByDayOutput,
        submitter_type=graphene_enum_type(SubmitterType)(
            required=False,
            description="Version utilisée pour le calcul des dépassements de seuil",
        ),
        description="Résultats de calcul de seuils règlementaires groupés par jour",
    )

    regulation_computations_by_week = graphene.List(
        RegulationComputationByWeekOutput,
        submitter_type=graphene_enum_type(SubmitterType)(
            required=False,
            description="Version utilisée pour le calcul des dépassements de seuil",
        ),
        description="Résultats de calcul de seuils règlementaires groupés par semaine",
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

    def resolve_regulation_computations_by_day(
        self, info, submitter_type=None
    ):
        base_query = RegulationComputation.query.filter(
            RegulationComputation.user_id == self.user.id,
            RegulationComputation.day >= self.history_start_date,
            RegulationComputation.day <= self.history_end_date,
        )
        if submitter_type:
            base_query = base_query.filter(
                RegulationComputation.submitter_type == submitter_type
            )
        regulation_computations = base_query.order_by(
            RegulationComputation.day
        ).all()
        regulation_computations_by_day = [
            RegulationComputationByDayOutput(
                day=day_, regulation_computations=list(computations_)
            )
            for day_, computations_ in groupby(
                regulation_computations, lambda x: x.day
            )
        ]
        return regulation_computations_by_day

    def resolve_regulation_computations_by_week(
        self, info, submitter_type=None
    ):
        base_query = RegulationComputation.query.filter(
            RegulationComputation.user_id == self.user.id,
            RegulationComputation.day >= self.history_start_date,
            RegulationComputation.day <= self.history_end_date,
            # 1 = Sunday, 2 = Monday, ..., 7 = Saturday.
            func.dayofweek(RegulationComputation.day) == 2,
        )
        if submitter_type:
            base_query = base_query.filter(
                RegulationComputation.submitter_type == submitter_type
            )
        regulation_computations = base_query.order_by(
            RegulationComputation.day
        ).all()
        regulation_computations_by_day = [
            RegulationComputationByWeekOutput(
                start_of_week=start_of_week_,
                regulation_computations=list(computations_),
            )
            for start_of_week_, computations_ in groupby(
                regulation_computations, lambda x: x.day
            )
        ]
        return regulation_computations_by_day
