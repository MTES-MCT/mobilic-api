import graphene
from sqlalchemy.orm import selectinload
from collections import defaultdict

from app.data_access.mission import MissionOutput
from app.domain.permissions import company_admin_at, belongs_to_company_at
from app.domain.work_days import group_user_missions_by_day, WorkDayStatsOnly
from app.helpers.authorization import with_authorization_policy, current_user
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.helpers.graphql import get_children_field_names
from app.models import Company, User
from app.models.activity import ActivityType
from app.models.company_known_address import CompanyKnownAddressOutput
from app.models.employment import (
    EmploymentOutput,
    Employment,
    EmploymentRequestValidationStatus,
)
from app.models.expenditure import ExpenditureType
from app.models.queries import query_company_missions, query_work_day_stats
from app.models.vehicle import VehicleOutput


class CompanyOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Company
        only_fields = (
            "id",
            "siren",
            "allow_team_mode",
            "require_kilometer_data",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant de l'entreprise"
    )
    siren = graphene.Field(
        graphene.Int,
        required=False,
        description="Numéro SIREN de l'entreprise",
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
        limit=graphene.Int(
            required=False,
            description="Nombre maximal de missions retournées, par ordre de récence.",
        ),
    )
    missions = graphene.List(
        MissionOutput,
        description="Liste des missions de l'entreprise",
        from_time=graphene.Date(
            required=False, description="Horodatage de début de l'historique"
        ),
        until_time=graphene.Date(
            required=False, description="Horodatage de fin de l'historique"
        ),
        limit=graphene.Int(
            required=False,
            description="Nombre maximal de missions retournées, par ordre de récence.",
        ),
        only_non_validated_missions=graphene.Boolean(
            required=False,
            description="Ne retourne que les missions qui n'ont pas encore été validées par le gestionnaire. Par défaut l'option n'est pas activée.",
        ),
    )
    vehicles = graphene.List(
        VehicleOutput, description="Liste des véhicules de l'entreprise"
    )
    employments = graphene.List(
        EmploymentOutput,
        description="Liste des rattachements validés ou en cours de validation de l'entreprise. Inclut également les rattachements qui ne sont plus actifs",
    )
    known_addresses = graphene.List(
        CompanyKnownAddressOutput,
        description="Liste des lieux enregistrés de l'entreprise",
    )
    allow_team_mode = graphene.Boolean(
        description="Indique si l'entreprise permet les saisies en mode équipe pour ses missions"
    )
    require_kilometer_data = graphene.Boolean(
        description="Indique si l'entreprise exige les données kilométriques en début et fin de mission"
    )

    def resolve_name(self, info):
        return self.name

    @with_authorization_policy(
        belongs_to_company_at,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'users' of company object.",
    )
    def resolve_users(self, info):
        info.context.company_ids_scope = [self.id]
        return self.query_users()

    @with_authorization_policy(
        belongs_to_company_at,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'vehicles' of company object.",
    )
    def resolve_vehicles(self, info):
        return [v for v in self.vehicles if not v.is_terminated]

    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'employments' of company object. Actor must be company admin.",
    )
    def resolve_employments(self, info):
        return (
            Employment.query.options(selectinload(Employment.user))
            .filter(
                Employment.company_id == self.id,
                ~Employment.is_dismissed,
                Employment.validation_status
                != EmploymentRequestValidationStatus.REJECTED,
            )
            .all()
        )

    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda self, info, **kwargs: self,
        error_message="Forbidden access to field 'missions' of company object. Actor must be company admin.",
    )
    def resolve_missions(
        self,
        info,
        from_time=None,
        until_time=None,
        limit=None,
        only_non_validated_missions=False,
    ):
        return query_company_missions(
            self.id,
            start_time=from_time,
            end_time=until_time,
            limit=limit,
            only_non_validated_missions=only_non_validated_missions,
        )

    @with_authorization_policy(
        company_admin_at,
        get_target_from_args=lambda self, info, **kwargs: self,
        error_message="Forbidden access to field 'workDays' of company object. Actor must be company admin.",
    )
    def resolve_work_days(
        self, info, from_date=None, until_date=None, limit=None
    ):
        # There are two ways to build the work days :
        ## - Either retrieve all objects at the finest level from the DB and compute aggregates on them, which is rather costly
        ## - Have the DB compute the aggregates and return them directly, which is the go-to approach if the low level items are not required
        if set(get_children_field_names(info)) & {"activities", "missions"}:
            missions = query_company_missions(
                self.id, start_time=from_date, end_time=until_date, limit=limit
            )

            user_to_missions = defaultdict(set)
            for mission in missions:
                for activity in mission.activities:
                    user_to_missions[activity.user].add(mission)

            work_days = sorted(
                [
                    work_day
                    for user, missions in user_to_missions.items()
                    for work_day in group_user_missions_by_day(
                        user, missions, from_date, until_date
                    )
                ],
                key=lambda wd: wd.day,
            )
            return work_days[-limit:]

        ## Efficient approach
        else:
            work_day_stats = query_work_day_stats(
                self.id, start_time=from_date, end_time=until_date, limit=limit
            )
            user_ids = set([row.user_id for row in work_day_stats])
            users = {user_id: User.query.get(user_id) for user_id in user_ids}
            wds = [
                WorkDayStatsOnly(
                    day=row.day,
                    user=users[row.user_id],
                    start_time=row.start_time,
                    end_time=row.end_time,
                    is_running=row.is_running,
                    service_duration=row.service_duration,
                    total_work_duration=row.total_work_duration,
                    activity_timers={
                        a_type: getattr(row, f"{a_type.value}_duration")
                        for a_type in ActivityType
                    },
                    expenditures={
                        e_type: getattr(row, f"n_{e_type.value}_expenditures")
                        for e_type in ExpenditureType
                    },
                    mission_names=row.mission_names,
                )
                for index, row in enumerate(work_day_stats)
            ]
            return wds

    @with_authorization_policy(
        belongs_to_company_at,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'knownAddresses' of company object.",
    )
    def resolve_known_addresses(self, info):
        return [a for a in self.known_addresses if not a.is_dismissed]


from app.data_access.user import UserOutput
from app.data_access.work_day import WorkDayOutput
