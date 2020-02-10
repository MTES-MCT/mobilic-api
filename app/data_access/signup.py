import graphene
from graphene_sqlalchemy import SQLAlchemyObjectType

from app.controllers.utils import request_data_schema
from app.data_access.activity import ActivityOutput
from app.domain.permissions import self_or_company_admin, belongs_to_company
from app.helpers.authorization import with_authorization_policy
from app.models import User, Company


@request_data_schema
class SignupPostData:
    email: str
    password: str
    first_name: str
    last_name: str
    company_id: int


@request_data_schema
class CompanySignupData:
    name: str


class UserOutput(SQLAlchemyObjectType):
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

    @with_authorization_policy(
        self_or_company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_activities(self, info):
        return self.acknowledged_activities


class CompanyOutput(SQLAlchemyObjectType):
    class Meta:
        model = Company
        only_fields = ("id", "name")

    users = graphene.List(UserOutput)

    @with_authorization_policy(
        belongs_to_company, get_target_from_args=lambda self, info: self
    )
    def resolve_users(self, info):
        return self.users
