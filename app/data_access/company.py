import graphene

from app.data_access.user import UserOutput
from app.domain.permissions import company_admin
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import Company
from app.models.vehicle import VehicleOutput


class CompanyOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Company
        only_fields = ("id", "name")

    users = graphene.List(UserOutput)
    vehicles = graphene.List(VehicleOutput)

    @with_authorization_policy(
        company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_users(self, info):
        return self.users

    @with_authorization_policy(
        company_admin, get_target_from_args=lambda self, info: self
    )
    def resolve_vehicles(self, info):
        return self.vehicles
