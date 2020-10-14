import graphene
from datetime import date

from app.data_access.mission import MissionOutput
from app.domain.permissions import (
    user_resolver_with_consultation_scope,
    only_self,
    self_or_company_admin,
)
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated,
)
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models import User, Company
from app.models.activity import ActivityOutput
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
    primary_company = graphene.Field(
        lambda: CompanyOutput,
        description="Entreprise de rattachement principale",
    )
    is_admin_of_primary_company = graphene.Field(
        graphene.Boolean,
        description="Précise si l'utilisateur est gestionnaire de son entreprise principale",
    )
    activities = graphene.Field(
        graphene.List(
            ActivityOutput,
            description="Liste complète des activités de l'utilisateur",
        ),
        from_time=TimeStamp(
            required=False, description="Horodatage de début de l'historique"
        ),
        until_time=TimeStamp(
            required=False, description="Horodatage de fin de l'historique"
        ),
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
        description="Liste complète des missions de l'utilisateur",
        from_time=TimeStamp(
            required=False, description="Horodatage de début de l'historique"
        ),
        until_time=TimeStamp(
            required=False, description="Horodatage de fin de l'historique"
        ),
    )
    current_employments = graphene.List(
        EmploymentOutput,
        description="Liste des rattachements actifs ou en attente de validation",
    )
    admined_companies = graphene.List(
        lambda: CompanyOutput,
        description="Liste des entreprises sur lesquelles l'utilisateur a les droits de gestion",
    )

    @with_authorization_policy(
        self_or_company_admin,
        get_target_from_args=lambda self, info: self,
        error_message="Unauthorized access to 'isAdminOfPrimaryCompany' field of user object.",
    )
    def resolve_is_admin_of_primary_company(self, info):
        current_primary_employment = self.primary_employment_at(date.today())
        return (
            current_primary_employment.has_admin_rights
            if current_primary_employment
            else None
        )

    @with_authorization_policy(authenticated)
    @user_resolver_with_consultation_scope(
        error_message="Unauthorized access to field 'activities' of user object. The field is only accessible to the user himself of company admins."
    )
    def resolve_activities(
        self, info, consultation_scope, from_time=None, until_time=None
    ):
        acknowledged_activities = self.query_activities_with_relations(
            start_time=from_time, end_time=until_time
        )
        if consultation_scope.company_ids:
            acknowledged_activities = [
                a
                for a in acknowledged_activities
                if a.mission.company_id in consultation_scope.company_ids
            ]
        return acknowledged_activities

    @with_authorization_policy(authenticated)
    @user_resolver_with_consultation_scope(
        error_message="Unauthorized access to field 'workDays' of user object. The field is only accessible to the user himself of company admins."
    )
    def resolve_work_days(
        self, info, consultation_scope, from_date=None, until_date=None
    ):
        return group_user_events_by_day(
            self,
            consultation_scope,
            from_date=from_date,
            until_date=until_date,
        )

    @with_authorization_policy(authenticated)
    @user_resolver_with_consultation_scope(
        error_message="Unauthorized access to field 'missions' of user object. The field is only accessible to the user himself of company admins."
    )
    def resolve_missions(
        self, info, consultation_scope, from_time=None, until_time=None
    ):
        missions = self.query_missions(
            start_time=from_time, end_time=until_time
        )
        if consultation_scope.company_ids:
            missions = [
                m
                for m in missions
                if m.company_id in consultation_scope.company_ids
            ]
        return missions

    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda self, info: self,
        error_message="Unauthorized access to field 'currentEmployments' of user object. The field is only accessible to the user himself.",
    )
    def resolve_current_employments(self, info):
        return self.employments_at(date.today(), with_pending_ones=True)

    @with_authorization_policy(
        only_self,
        get_target_from_args=lambda self, info: self,
        error_message="Unauthorized access to field 'adminedCompanies' of user object. The field is only accessible to the user himself.",
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
from app.data_access.work_day import WorkDayOutput
