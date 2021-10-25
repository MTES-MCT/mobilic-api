import graphene
from datetime import date, datetime
from sqlalchemy import desc, or_, and_

from app.data_access.mission import MissionConnection
from app.domain.permissions import (
    user_resolver_with_consultation_scope,
    only_self,
)
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.authorization import (
    with_authorization_policy,
)
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.helpers.pagination import (
    paginate_query,
    parse_datetime_plus_id_cursor,
    to_connection,
)
from app.helpers.time import (
    get_max_datetime,
    get_min_datetime,
    max_or_none,
    min_or_none,
)
from app.models import User, Company, Activity, Mission
from app.data_access.activity import ActivityConnection
from app.models.employment import EmploymentOutput


class UserOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = User
        only_fields = (
            "id",
            "first_name",
            "last_name",
            "email",
            "has_confirmed_email",
            "has_activated_email",
            "disabled_warnings",
        )

    id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant Mobilic de l'utilisateur",
    )
    first_name = graphene.Field(
        graphene.String, required=True, description="Prénom"
    )
    last_name = graphene.Field(
        graphene.String, required=True, description="Nom"
    )
    birth_date = graphene.Field(
        graphene.String,
        description="Date de naissance de l'utilisateur. Uniquement disponible pour les utilisateurs qui se sont inscrits via FranceConnect.",
    )
    email = graphene.Field(
        graphene.String,
        required=False,
        description="Adresse email, qui sert également d'identifiant de connexion",
    )
    activities = graphene.Field(
        ActivityConnection,
        description="Liste des activités de l'utilisateur, triées par id (pas forcément par récence).",
        from_time=TimeStamp(
            required=False, description="Horodatage de début de l'historique"
        ),
        until_time=TimeStamp(
            required=False, description="Horodatage de fin de l'historique"
        ),
        first=graphene.Argument(
            graphene.Int,
            description="Nombre maximum d'activités retournées (taille de la page), conformément aux spécifications sur les cursor connections.",
        ),
        after=graphene.Argument(
            graphene.String,
            description="Valeur du curseur, qui détermine quelle page retourner.",
        ),
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
        first=graphene.Argument(graphene.Int, required=False),
        after=graphene.Argument(graphene.String, required=False),
    )
    missions = graphene.Field(
        MissionConnection,
        description="Liste des missions de l'utilisateur, triées par récence.",
        from_time=TimeStamp(
            required=False, description="Horodatage de début de l'historique"
        ),
        until_time=TimeStamp(
            required=False, description="Horodatage de fin de l'historique"
        ),
        first=graphene.Argument(
            graphene.Int,
            description="Nombre maximum de missions retournées (taille de la page), conformément aux spécifications sur les cursor connections.",
        ),
        after=graphene.Argument(
            graphene.String,
            description="Valeur du curseur, qui détermine quelle page retourner.",
        ),
    )
    current_employments = graphene.List(
        EmploymentOutput,
        description="Liste des rattachements actifs ou en attente de validation",
    )
    employments = graphene.List(
        EmploymentOutput,
        description="Liste de tous les rattachements actifs on en attente de validation de l'utilisateur sur une période donnée",
        from_date=graphene.Date(required=False, description="Date de début"),
        until_date=graphene.Date(required=False, description="Date de fin"),
    )
    admined_companies = graphene.List(
        lambda: CompanyOutput,
        description="Liste des entreprises sur lesquelles l'utilisateur a les droits de gestion",
    )

    @user_resolver_with_consultation_scope(
        error_message="Forbidden access to field 'activities' of user object. The field is only accessible to the user himself of company admins."
    )
    def resolve_activities(
        self,
        info,
        consultation_scope,
        from_time=None,
        until_time=None,
        first=None,
        after=None,
    ):
        from_time = get_max_datetime(
            from_time, consultation_scope.user_data_min_date
        )
        until_time = get_min_datetime(
            until_time, consultation_scope.user_data_max_date
        )

        acknowledged_activity_query = self.query_activities_with_relations(
            start_time=from_time,
            end_time=until_time,
            restrict_to_company_ids=consultation_scope.company_ids or None,
        )

        def cursor_to_filter(cursor_string):
            start_time, id_ = cursor_string.split(",")
            start_time = datetime.fromisoformat(start_time)
            id_ = int(id_)
            return or_(
                Activity.start_time < start_time,
                and_(Activity.start_time == start_time, Activity.id < id_),
            )

        return paginate_query(
            acknowledged_activity_query,
            item_to_cursor=lambda activity: f"{str(activity.start_time)},{activity.id}",
            cursor_to_filter=cursor_to_filter,
            orders=(desc(Activity.start_time), desc(Activity.id)),
            connection_cls=ActivityConnection,
            after=after,
            first=first,
            max_first=200,
        )

    @user_resolver_with_consultation_scope(
        error_message="Forbidden access to field 'workDays' of user object. The field is only accessible to the user himself of company admins."
    )
    def resolve_work_days(
        self,
        info,
        consultation_scope,
        from_date=None,
        until_date=None,
        first=None,
        after=None,
    ):
        from_time = get_max_datetime(
            from_date, consultation_scope.user_data_min_date
        )
        until_time = get_min_datetime(
            until_date, consultation_scope.user_data_max_date
        )

        actual_first = min(first or 200, 200)
        work_days, has_next = group_user_events_by_day_with_limit(
            self,
            consultation_scope,
            from_date=from_time.date() if from_time else None,
            until_date=until_time.date() if until_time else None,
            first=actual_first,
            after=after,
        )
        reverse_work_days = sorted(
            work_days, key=lambda wd: wd.day, reverse=True
        )

        return to_connection(
            reverse_work_days,
            connection_cls=WorkDayConnection,
            has_next_page=has_next,
            get_cursor=lambda wd: str(wd.day),
            first=actual_first,
        )

    @user_resolver_with_consultation_scope(
        error_message="Forbidden access to field 'missions' of user object. The field is only accessible to the user himself of company admins."
    )
    def resolve_missions(
        self,
        info,
        consultation_scope,
        from_time=None,
        until_time=None,
        first=None,
        after=None,
    ):
        from_time = get_max_datetime(
            from_time, consultation_scope.user_data_min_date
        )
        until_time = get_min_datetime(
            until_time, consultation_scope.user_data_max_date
        )

        if after:
            max_time, after_mission_id = parse_datetime_plus_id_cursor(after)
            until_time = min(until_time, max_time) if until_time else max_time

        def additional_activity_filters(query):
            if after:
                query = query.filter(
                    or_(
                        Activity.start_time < max_time,
                        and_(
                            Activity.start_time == max_time,
                            Activity.mission_id < after_mission_id,
                        ),
                    )
                )

            query = query.order_by(
                desc(Activity.start_time), desc(Activity.mission_id)
            )
            return query

        actual_first = min(first or 200, 200)
        missions, has_next_page = self.query_missions_with_limit(
            start_time=from_time,
            end_time=until_time,
            restrict_to_company_ids=consultation_scope.company_ids or None,
            additional_activity_filters=additional_activity_filters,
            sort_activities=False,
            limit_fetch_activities=actual_first * 5,
        )
        return to_connection(
            missions,
            connection_cls=MissionConnection,
            get_cursor=lambda m: f"{str(m.activities_for(self)[0].start_time)},{m.id}",
            has_next_page=has_next_page,
            first=actual_first,
        )

    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'currentEmployments' of user object. The field is only accessible to the user himself.",
    )
    def resolve_current_employments(self, info):
        return sorted(
            self.active_employments_at(
                date.today(), include_pending_ones=True
            ),
            key=lambda e: e.start_date,
        )

    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'employments' of user object. The field is only accessible to the user himself.",
    )
    @user_resolver_with_consultation_scope()
    def resolve_employments(
        self, info, consultation_scope, from_date=None, until_date=None
    ):
        from_date = max_or_none(
            from_date, consultation_scope.user_data_min_date
        )
        until_date = min_or_none(
            until_date, consultation_scope.user_data_max_date
        )

        employments_with_eventual_duplicates = sorted(
            self.active_employments_between(
                from_date, until_date, include_pending_ones=False
            ),
            key=lambda e: e.start_date,
            reverse=True,
        )
        company_ids = set()
        deduplicated_employments = []
        for e in employments_with_eventual_duplicates:
            if e.company_id not in company_ids:
                deduplicated_employments.append(e)
                company_ids.add(e.company_id)
        return reversed(deduplicated_employments)

    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda self, info: self,
        error_message="Forbidden access to field 'adminedCompanies' of user object. The field is only accessible to the user himself.",
    )
    def resolve_admined_companies(self, info):
        return Company.query.filter(
            Company.id.in_(self.current_company_ids_with_admin_rights)
        ).all()

    def resolve_birth_date(self, info):
        return (
            self.france_connect_info.get("birthdate")
            if self.france_connect_info
            else None
        )


from app.data_access.company import CompanyOutput
from app.data_access.work_day import WorkDayConnection
