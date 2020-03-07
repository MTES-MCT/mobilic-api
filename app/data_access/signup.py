import graphene

from app.data_access.activity import ActivityOutput
from app.data_access.comment import CommentOutput
from app.data_access.expenditure import ExpenditureOutput
from app.data_access.work_day import WorkDayOutput
from app.domain.permissions import self_or_company_admin, belongs_to_company
from app.domain.work_days import group_user_events_by_day
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import User, Company


class UserOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = User
        only_fields = (
            "id",
            "first_name",
            "last_name",
            "company",
            "is_company_admin",
        )

    activities = graphene.List(ActivityOutput)
    expenditures = graphene.List(ExpenditureOutput)
    comments = graphene.List(CommentOutput)
    work_days = graphene.List(WorkDayOutput)

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_activities(self, info):
        return self.acknowledged_activities

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_expenditures(self, info):
        return self.acknowledged_expenditures

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_comments(self, info):
        return self.comments

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_work_days(self, info):
        return group_user_events_by_day(self)


class CompanyOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Company
        only_fields = ("id", "name")

    users = graphene.List(UserOutput)

    @with_authorization_policy(
        belongs_to_company, get_target_from_args=lambda self, info: self
    )
    def resolve_users(self, info):
        return self.users
