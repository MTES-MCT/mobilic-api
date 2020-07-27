import graphene

from app.data_access.user import UserOutput
from app.domain.permissions import company_admin_at
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import Company
from app.models.employment import (
    EmploymentOutput,
    EmploymentRequestValidationStatus,
)
from app.models.vehicle import VehicleOutput


class CompanyOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Company
        only_fields = ("id",)

    name = graphene.Field(graphene.String)
    users = graphene.List(UserOutput)
    vehicles = graphene.List(VehicleOutput)
    employments = graphene.List(EmploymentOutput)

    def resolve_name(self, info):
        return self.name

    @with_authorization_policy(
        company_admin_at, get_target_from_args=lambda self, info: self
    )
    def resolve_users(self, info):
        info.context.company_ids_scope = [self.id]
        return self.users

    @with_authorization_policy(
        company_admin_at, get_target_from_args=lambda self, info: self
    )
    def resolve_vehicles(self, info):
        return [v for v in self.vehicles if not v.is_terminated]

    @with_authorization_policy(
        company_admin_at, get_target_from_args=lambda self, info: self
    )
    def resolve_employments(self, info):
        return [e for e in self.employments if e.is_not_rejected]
