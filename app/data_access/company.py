import graphene
from sqlalchemy.orm import selectinload
from collections import defaultdict

from app.data_access.mission import MissionOutput
from app.domain.permissions import company_admin_at, belongs_to_company_at
from app.domain.work_days import group_user_missions_by_day
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models import Company, Mission, Activity
from app.models.employment import EmploymentOutput
from app.models.queries import query_company_missions
from app.models.vehicle import VehicleOutput


class CompanyOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Company
        only_fields = ("id", "siren")

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant de l'entreprise"
    )
    siren = graphene.Field(
        graphene.Int, required=True, description="Numéro SIREN de l'entreprise"
    )
    name = graphene.Field(graphene.String, description="Nom de l'entreprise")
    users = graphene.List(
        lambda: UserOutput,
        description="Liste des utilisateurs rattachés à l'entreprise",
    )
    work_days = graphene.List(
        lambda: WorkDayOutput,
        description="Regroupement des missions et activités par journée calendaire",
        from_date=graphene.Date(
            required=False, description="Date de début de l'historique"
        ),
        until_date=graphene.Date(
            required=False, description="Date de fin de l'historique"
        ),
    )
    missions = graphene.List(
        MissionOutput,
        description="Liste complète des missions de l'entreprise",
    )
    vehicles = graphene.List(
        VehicleOutput, description="Liste des véhicules de l'entreprise"
    )
    employments = graphene.List(
        EmploymentOutput,
        description="Liste des rattachements validés ou en cours de validation de l'entreprise. Inclut également les rattachements qui ne sont plus actifs",
    )

    def resolve_name(self, info):
        return self.name

    @with_authorization_policy(
        belongs_to_company_at,
        get_target_from_args=lambda self, info: self,
        error_message="Unauthorized access to field 'users' of company object.",
    )
    def resolve_users(self, info):
        info.context.company_ids_scope = [self.id]
        return self.query_users()

    @with_authorization_policy(
        belongs_to_company_at,
        get_target_from_args=lambda self, info: self,
        error_message="Unauthorized access to field 'vehicles' of company object.",
    )
    def resolve_vehicles(self, info):
        return [v for v in self.vehicles if not v.is_terminated]

    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda self, info: self,
        error_message="Unauthorized access to field 'employments' of company object. Actor must be company admin.",
    )
    def resolve_employments(self, info):
        return [
            e
            for e in self.employments
            if e.is_not_rejected and not e.is_dismissed
        ]

    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda self, info: self,
        error_message="Unauthorized access to field 'missions' of company object. Actor must be company admin.",
    )
    def resolve_missions(self, info):
        return (
            Mission.query.options(selectinload(Mission.validations))
            .options(selectinload(Mission.expenditures))
            .options(
                selectinload(Mission.activities).selectinload(Activity.revisee)
            )
            .filter(Mission.company_id == self.id)
        )

    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda self, info, **kwargs: self,
        error_message="Unauthorized access to field 'workDays' of company object. Actor must be company admin.",
    )
    def resolve_work_days(self, info, from_date=None, until_date=None):
        missions = query_company_missions(
            self.id, start_time=from_date, end_time=until_date
        )
        user_to_missions = defaultdict(set)
        for mission in missions:
            for activity in mission.activities:
                user_to_missions[activity.user].add(mission)

        return sorted(
            [
                work_day
                for user, missions in user_to_missions.items()
                for work_day in group_user_missions_by_day(user, missions)
            ],
            key=lambda wd: wd.start_time,
        )


from app.data_access.user import UserOutput
from app.data_access.work_day import WorkDayOutput
