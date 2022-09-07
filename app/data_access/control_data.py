import graphene

from app import app
from app.data_access.mission import MissionOutput
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.controller_control import ControllerControl
from app.models.employment import EmploymentOutput


def compute_history_start_date(qr_code_generation_time):
    return qr_code_generation_time - app.config["USER_CONTROL_HISTORY_DEPTH"]


class ControllerControlOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ControllerControl

    qr_code_generation_time = graphene.Field(TimeStamp, required=True)
    creation_time = graphene.Field(TimeStamp, required=True)

    employments = graphene.List(
        EmploymentOutput,
        description="Liste des rattachements actifs au moment du contrôle",
    )

    missions = graphene.List(
        MissionOutput,
        mission_id=graphene.Int(
            required=False,
            description="Filter the outputed mission ton only this mission id",
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
