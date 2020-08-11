import graphene
from datetime import date

from app.data_access.mission import MissionOutput
from app.data_access.work_day import WorkDayOutput
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
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import User
from app.models.activity import ActivityOutput
from app.models.employment import EmploymentOutput


class UserOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = User
        only_fields = ("id", "first_name", "last_name", "email")

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
    email = graphene.Field(
        graphene.String,
        required=False,
        description="Adresse email, qui sert également d'identifiant de connexion",
    )
    company = graphene.Field(
        lambda: CompanyOutput,
        description="Entreprise de rattachement principale",
    )
    is_company_admin = graphene.Field(
        graphene.Boolean,
        description="Précise si l'utilisateur est gestionnaire de son entreprise principale",
    )
    activities = graphene.List(
        ActivityOutput,
        description="Liste complète des activités de l'utilisateur",
    )
    work_days = graphene.List(
        WorkDayOutput,
        description="Regroupement des missions et activités par journée calendaire",
    )
    missions = graphene.List(
        MissionOutput,
        description="Liste complète des missions de l'utilisateur",
    )
    current_employments = graphene.List(
        EmploymentOutput,
        description="Liste des rattachements actifs ou en attente de validation",
    )

    def resolve_company(self, info):
        return self.primary_company

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_is_company_admin(self, info):
        current_primary_employment = self.primary_employment_at(date.today())
        return (
            current_primary_employment.has_admin_rights
            if current_primary_employment
            else None
        )

    @with_authorization_policy(authenticated)
    @user_resolver_with_consultation_scope
    def resolve_activities(self, info, consultation_scope):
        acknowledged_activities = self.acknowledged_activities
        if consultation_scope.company_ids:
            acknowledged_activities = [
                a
                for a in acknowledged_activities
                if a.mission.company_id in consultation_scope.company_ids
            ]
        return acknowledged_activities

    @with_authorization_policy(authenticated)
    @user_resolver_with_consultation_scope
    def resolve_work_days(self, info, consultation_scope):
        return group_user_events_by_day(self, consultation_scope)

    @with_authorization_policy(authenticated)
    @user_resolver_with_consultation_scope
    def resolve_missions(self, info, consultation_scope):
        missions = self.missions()
        if consultation_scope.company_ids:
            missions = [
                m
                for m in missions
                if m.company_id in consultation_scope.company_ids
            ]
        return missions

    @with_authorization_policy(
        only_self, get_target_from_args=lambda self, info: self
    )
    def resolve_current_employments(self, info):
        return self.employments_at(date.today(), with_pending_ones=True)


from app.data_access.company import CompanyOutput
