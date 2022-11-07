import graphene

from app import app
from app.data_access.mission import MissionOutput
from app.data_access.regulation_computation import RegulationComputationOutput
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
    graphene_enum_type,
)
from app.helpers.submitter_type import SubmitterType
from app.models.controller_control import ControllerControl
from app.models.employment import EmploymentOutput
from app.models.regulation_computation import RegulationComputation


def compute_history_start_date(qr_code_generation_time):
    return qr_code_generation_time - app.config["USER_CONTROL_HISTORY_DEPTH"]


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

    regulation_computations = graphene.List(
        RegulationComputationOutput,
        submitter_type=graphene_enum_type(SubmitterType)(
            required=False,
            description="Version utilisée pour le calcul des dépassements de seuil",
        ),
        description="Résultats de calcul de seuils règlementaires",
    )

    def resolve_employments(
        self,
        info,
    ):
        from_date = compute_history_start_date(
            self.qr_code_generation_time.date()
        )
        until_date = self.qr_code_generation_time.date()

        employments = sorted(
            self.user.active_employments_between(
                from_date, until_date, include_pending_ones=False
            ),
            key=lambda e: e.start_date,
            reverse=True,
        )
        return employments

    def resolve_missions(self, info, mission_id=None):
        from_date = compute_history_start_date(
            self.qr_code_generation_time.date()
        )
        until_date = self.qr_code_generation_time.date()

        missions, has_next_page = self.user.query_missions_with_limit(
            start_time=from_date,
            end_time=until_date,
            limit_fetch_activities=2000,
            max_reception_time=self.qr_code_generation_time,
            mission_id=mission_id,
            include_dismissed_activities=True,
        )
        return missions

    def resolve_history_start_date(self, info):
        return compute_history_start_date(self.qr_code_generation_time.date())

    def resolve_regulation_computations(self, info, submitter_type=None):
        from_date = compute_history_start_date(
            self.qr_code_generation_time.date()
        )
        until_date = self.qr_code_generation_time.date()

        base_query = RegulationComputation.query.filter(
            RegulationComputation.user_id == self.user.id,
            RegulationComputation.day >= from_date,
            RegulationComputation.day <= until_date,
        )
        if submitter_type:
            base_query = base_query.filter(
                RegulationComputation.submitter_type == submitter_type
            )
        print(base_query)
        return base_query.order_by(RegulationComputation.day).all()
