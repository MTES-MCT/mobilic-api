from dateutil.relativedelta import relativedelta
from flask import g

from app.data_access.business import BusinessOutput
from app.data_access.company_certification import CompanyCertificationType
from app.data_access.regulation_computation import (
    get_regulation_checks_by_unit,
)
from app.data_access.regulatory_alerts_summary import (
    RegulatoryAlertsSummary,
    AlertsGroup,
)
from app.data_access.work_day import WorkDayConnection
from app.data_access.user import UserOutput
from datetime import date

import graphene
from sqlalchemy import desc, func
from sqlalchemy.orm import selectinload

from app.data_access.employment import EmploymentOutput, OAuth2ClientOutput
from app.data_access.mission import MissionConnection
from app.data_access.team import TeamOutput
from app.domain.company import (
    check_company_has_no_activities,
    has_any_active_admin,
)
from app.domain.permissions import (
    company_admin,
    is_employed_by_company_over_period,
    has_any_employment_with_company_or_controller,
)
from app.domain.work_days import WorkDayStatsOnly
from app.helpers.authorization import (
    with_authorization_policy,
    controller_only,
)
from app.helpers.errors import AuthorizationError
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
    ShortMonth,
)
from app.helpers.pagination import to_connection
from app.helpers.time import to_datetime
from app.models import Company, User, Mission, Activity, RegulatoryAlert
from app.models.activity import ActivityType
from app.models.company_known_address import CompanyKnownAddressOutput
from app.models.employment import (
    Employment,
    EmploymentRequestValidationStatus,
)
from app.models.expenditure import ExpenditureType
from app.models.queries import query_company_missions, query_work_day_stats
from app.models.regulation_check import UnitType, RegulationCheckType
from app.models.vehicle import VehicleOutput


class CompanySettings(graphene.ObjectType):
    allow_team_mode = graphene.Boolean(
        description="Indique si l'entreprise permet les saisies en mode équipe pour ses missions"
    )
    allow_transfers = graphene.Boolean(
        description="Indique si l'entreprise permet de saisir des temps de liaison"
    )
    require_kilometer_data = graphene.Boolean(
        description="Indique si l'entreprise exige les données kilométriques en début et fin de mission"
    )
    require_expenditures = graphene.Boolean(
        description="Indique si l'entreprise utilise le module Mobilic de saisie des frais."
    )
    require_support_activity = graphene.Boolean(
        description="Indique si l'entreprise établit une distinction entre conduite et accompagnement dans les activités."
    )
    require_mission_name = graphene.Boolean(
        description="Indique si un nom doit être saisi à la création de chaque mission."
    )
    allow_other_task = graphene.Boolean(
        description="Indique si l'entreprise permet de saisir des activités de type 'Autre tâche'"
    )
    other_task_label = graphene.String(
        description="Sous-titre de l'activité de type 'Autre tâche'"
    )


class CompanyOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Company
        only_fields = (
            "id",
            "siren",
            "phone_number",
            "business",
            "has_ceased_activity",
            "number_workers",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant de l'entreprise"
    )
    siren = graphene.Field(
        graphene.String,
        required=False,
        description="Numéro SIREN de l'entreprise",
    )
    phone_number = graphene.Field(
        graphene.String,
        required=False,
        description="Numéro de téléphone de l'entreprise",
    )
    business = graphene.Field(
        lambda: BusinessOutput,
        description="Type d'activités effectuées par l'entreprise",
    )
    nb_workers = graphene.Field(
        graphene.Int,
        required=False,
        description="Nombre de salariés déclarés par l'entreprise",
    )
    name = graphene.Field(graphene.String, description="Nom de l'entreprise")
    legal_name = graphene.Field(
        graphene.String, description="Nom légal de l'entreprise"
    )
    users = graphene.List(
        lambda: UserOutput,
        description="Liste des utilisateurs rattachés à l'entreprise",
        from_date=graphene.Date(
            required=False,
            description="Début de la période pendant laquelle le salarié doit être actif.",
        ),
        to_date=graphene.Date(
            required=False,
            description="Fin de la période pendant laquelle le salarié doit être actif.",
        ),
    )
    current_users = graphene.List(
        lambda: UserOutput,
        description="Liste des utilisateurs avec un rattachement actif à l'entreprise",
    )
    work_days = graphene.Field(
        lambda: WorkDayConnection,
        description="Regroupement des missions et activités par journée calendaire",
        from_date=graphene.Date(
            required=False, description="Date de début de l'historique"
        ),
        until_date=graphene.Date(
            required=False, description="Date de fin de l'historique"
        ),
        first=graphene.Int(
            required=False,
            description="Nombre maximal de journées de travail retournées, par ordre de récence.",
        ),
        after=graphene.String(
            required=False,
            description="Curseur de connection GraphQL, utilisé pour la pagination",
        ),
    )
    missions = graphene.Field(
        MissionConnection,
        description="Liste des missions de l'entreprise",
        from_time=TimeStamp(
            required=False, description="Horodatage de début de l'historique"
        ),
        until_time=TimeStamp(
            required=False, description="Horodatage de fin de l'historique"
        ),
        after=graphene.String(
            required=False,
            description="Curseur de connection, utilisé pour la pagination.",
        ),
        first=graphene.Int(
            required=False,
            description="Nombre maximal de missions retournées, par ordre de récence.",
        ),
        only_ended_missions=graphene.Boolean(
            required=False,
            description="Ne retourne que les missions qui sont terminées par tous leurs utilisateurs.",
        ),
    )
    missions_deleted = graphene.Field(
        MissionConnection,
        description="Liste des missions supprimées de l'entreprise",
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
    settings = graphene.Field(
        CompanySettings, description="Paramètres de saisie"
    )
    sirets = graphene.List(
        graphene.String,
        description="Liste des SIRETS des établissements regroupés dans cette entreprise",
    )
    teams = graphene.List(
        TeamOutput,
        description="Liste des équipes d'une entreprise",
    )
    authorized_clients = graphene.List(OAuth2ClientOutput)
    has_no_activity = graphene.Boolean(
        description="Indique que l'entreprise n'a jamais eu d'activité enregistrée"
    )
    current_admins = graphene.List(
        lambda: UserOutput,
        description="Liste des gestionnaires actuellement rattachés à l'entreprise",
    )
    has_no_active_admins = graphene.Boolean(
        description="Indique si l'entreprise n'a aucun gestionnaire ayant accepté les CGU"
    )
    current_company_certification = graphene.Field(
        CompanyCertificationType,
        description="Informations relatives au certificat en cours pour l'entreprise",
    )
    regulatory_alerts_recap = graphene.Field(
        RegulatoryAlertsSummary,
        description="Résumé des alertes règlementaires au cours d'un mois donné",
        month=ShortMonth(required=True),
        unique_user_id=graphene.Int(
            required=False,
            description="Identifiant d'un des salariés de l'entreprise",
        ),
    )

    def resolve_name(self, info):
        return self.name

    def resolve_nb_workers(self, info):
        return self.number_workers

    def resolve_teams(self, info):
        return self.teams

    @with_authorization_policy(
        is_employed_by_company_over_period,
        get_target_from_args=lambda self, info, **kwargs: self,
        error_message="Forbidden access to field 'users' of company object.",
    )
    def resolve_users(self, info, from_date=None, to_date=None):
        info.context.company_ids_scope = [self.id]
        return g.dataloaders["users"].load_many(
            self.users_ids_between(from_date, to_date)
        )

    @with_authorization_policy(
        is_employed_by_company_over_period,
        get_target_from_args=lambda self, info, **kwargs: self,
        error_message="Forbidden access to field 'current_users' of company object.",
    )
    def resolve_current_users(self, info):
        info.context.company_ids_scope = [self.id]
        return g.dataloaders["users"].load_many(
            self.users_ids_between(start=date.today(), end=date.today())
        )

    @with_authorization_policy(
        has_any_employment_with_company_or_controller,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'vehicles' of company object.",
    )
    def resolve_vehicles(self, info):
        vehicles = g.dataloaders["vehicles_in_company"].load(self.id)
        return vehicles.then(
            lambda vehicles: [v for v in vehicles if not v.is_terminated]
        )

    @with_authorization_policy(
        company_admin,
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
        company_admin,
        get_target_from_args=lambda self, info, **kwargs: self,
        error_message="Forbidden access to field 'missions' of company object. Actor must be company admin.",
    )
    def resolve_missions(
        self,
        info,
        from_time=None,
        until_time=None,
        only_ended_missions=False,
        first=None,
        after=None,
    ):
        return query_company_missions(
            [self.id],
            start_time=from_time,
            end_time=until_time,
            first=first,
            after=after,
            only_ended_missions=only_ended_missions,
        )

    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda self, info, **kwargs: self,
        error_message="Forbidden access to field 'missions' of company object. Actor must be a company admin.",
    )
    def resolve_missions_deleted(self, info):
        deleted_missions = (
            Mission.query.filter(
                Mission.company_id == self.id,
            )
            .join(Activity, Activity.mission_id == Mission.id)
            .group_by(Mission.id)
            .having(func.every(Activity.dismissed_at.isnot(None)))
        ).all()

        edges = [{"node": mission} for mission in deleted_missions]

        return MissionConnection(edges=edges)

    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda self, info, **kwargs: self,
        error_message="Forbidden access to field 'workDays' of company object. Actor must be company admin.",
    )
    def resolve_work_days(
        self, info, from_date=None, until_date=None, first=None, after=None
    ):
        # There are two ways to build the work days :
        # - Either retrieve all objects at the finest level from the DB and compute aggregates on them, which is rather costly
        # - Have the DB compute the aggregates and return them directly, which is the go-to approach if the low level items are not required
        # if set(get_children_field_names(info)) & {"activities", "missions"}:
        #     missions = query_company_missions(
        #         [self.id],
        #         start_time=from_date,
        #         end_time=until_date,
        #         limit=limit,
        #     )
        #
        #     user_to_missions = defaultdict(set)
        #     for mission in missions:
        #         for activity in mission.activities:
        #             user_to_missions[activity.user].add(mission)
        #
        #     work_days = sorted(
        #         [
        #             work_day
        #             for user, missions in user_to_missions.items()
        #             for work_day in group_user_missions_by_day(
        #                 user, missions, from_date, until_date
        #             )
        #         ],
        #         key=lambda wd: wd.day,
        #     )
        #     return work_days[-limit:] if limit else work_days

        # Efficient approach
        work_day_stats, has_next_page = query_work_day_stats(
            self.id,
            start_date=from_date,
            end_date=until_date,
            first=first,
            after=after,
        )
        user_ids = set([row.user_id for row in work_day_stats])

        users = User.query.filter(User.id.in_(user_ids))
        users = {user.id: user for user in users}
        wds = [
            WorkDayStatsOnly(
                day=row.day,
                user=users[row.user_id],
                start_time=row.start_time,
                last_activity_start_time=row.last_activity_start_time,
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
                mission_names={mn[0]: mn[1] for mn in row.mission_names},
            )
            for index, row in enumerate(work_day_stats)
            if row.service_duration > 0
        ]

        return to_connection(
            wds,
            connection_cls=WorkDayConnection,
            has_next_page=has_next_page,
            get_cursor=lambda wd: f"{str(to_datetime(wd.day))},{wd.user.id}",
            first=first,
        )

    @with_authorization_policy(
        has_any_employment_with_company_or_controller,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'knownAddresses' of company object.",
    )
    def resolve_known_addresses(self, info):
        return [a for a in self.known_addresses if not a.is_dismissed]

    def resolve_settings(self, info):
        return CompanySettings(
            **{
                k: getattr(self, k)
                for k in CompanySettings._meta.fields.keys()
            }
        )

    def resolve_sirets(self, info):
        return (
            [
                f"{self.siren}{str(short_siret).zfill(5)}"
                for short_siret in self.short_sirets
            ]
            if self.short_sirets
            else ""
        )

    def resolve_authorized_clients(self, info):
        return self.retrieve_authorized_clients

    def resolve_has_no_activity(self, info):
        return check_company_has_no_activities(self.id)

    @with_authorization_policy(
        controller_only,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'currentAdmins' of company object.",
    )
    def resolve_current_admins(self, info):
        return self.get_admins(date.today(), None)

    def resolve_has_no_active_admins(self, info):
        return not has_any_active_admin(self)

    def resolve_current_company_certification(self, info):
        return CompanyCertificationType.from_company_id(self.id)

    @with_authorization_policy(
        company_admin,
        get_target_from_args=lambda self, info, **kwargs: self,
        error_message="Forbidden access to field 'resolve_regulatory_alerts_recap' of company object. Actor must be company admin.",
    )
    def resolve_regulatory_alerts_recap(
        self, info, month, unique_user_id=None
    ):

        company_user_ids = [u.id for u in self.users]
        if unique_user_id and unique_user_id not in company_user_ids:
            raise AuthorizationError("Employee is not part of the company")

        user_ids = [unique_user_id] if unique_user_id else company_user_ids

        def query_alerts(_start_date, _end_date, _user_ids, count_only=True):
            query = RegulatoryAlert.query.filter(
                RegulatoryAlert.user_id.in_(_user_ids),
                RegulatoryAlert.day >= _start_date,
                RegulatoryAlert.day < _end_date,
            )
            if count_only:
                return query.count()
            return query.all()

        start_date = month
        end_date = month + relativedelta(months=1)

        current_month_alerts = query_alerts(
            _start_date=start_date,
            _end_date=end_date,
            _user_ids=user_ids,
            count_only=False,
        )
        previous_start = month + relativedelta(months=-1)
        previous_month_alerts_count = query_alerts(
            _start_date=previous_start,
            _end_date=start_date,
            _user_ids=user_ids,
        )

        daily_checks = get_regulation_checks_by_unit(
            unit=UnitType.DAY, date=start_date
        )
        daily_alerts = []
        for check in daily_checks:
            if check.type == RegulationCheckType.NO_LIC:
                continue
            if check.type == RegulationCheckType.ENOUGH_BREAK:
                alerts = [
                    a
                    for a in current_month_alerts
                    if a.regulation_check_id == check.id
                ]
                not_enough_break_alerts = [
                    a for a in alerts if a.extra["not_enough_break"]
                ]
                daily_alerts.append(
                    AlertsGroup(
                        alerts_type="not_enough_break",
                        nb_alerts=len(not_enough_break_alerts),
                        days=[],
                    )
                )
                too_much_uninterrupted_work_time_alerts = [
                    a
                    for a in alerts
                    if a.extra["too_much_uninterrupted_work_time"]
                ]
                daily_alerts.append(
                    AlertsGroup(
                        alerts_type="too_much_uninterrupted_work_time",
                        nb_alerts=len(too_much_uninterrupted_work_time_alerts),
                        days=[],
                    )
                )
                continue

            alerts = [
                a
                for a in current_month_alerts
                if a.regulation_check_id == check.id
            ]
            daily_alerts.append(
                AlertsGroup(
                    alerts_type=check.type, nb_alerts=len(alerts), days=[]
                )
            )

        weekly_checks = get_regulation_checks_by_unit(
            unit=UnitType.WEEK, date=start_date
        )
        weekly_alerts = []
        for check in weekly_checks:
            alerts = [
                a
                for a in current_month_alerts
                if a.regulation_check_id == check.id
            ]
            weekly_alerts.append(
                AlertsGroup(
                    alerts_type=check.type, nb_alerts=len(alerts), days=[]
                )
            )

        return RegulatoryAlertsSummary(
            month=month,
            total_nb_alerts=len(current_month_alerts),
            total_nb_alerts_previous_month=previous_month_alerts_count,
            daily_alerts=daily_alerts,
            weekly_alerts=weekly_alerts,
        )
