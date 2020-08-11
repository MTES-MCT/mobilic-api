import graphene

from app.domain.permissions import company_admin_at, belongs_to_company_at
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import Company
from app.models.employment import EmploymentOutput
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
        belongs_to_company_at, get_target_from_args=lambda self, info: self
    )
    def resolve_users(self, info):
        info.context.company_ids_scope = [self.id]
        return self.users

    @with_authorization_policy(
        belongs_to_company_at, get_target_from_args=lambda self, info: self
    )
    def resolve_vehicles(self, info):
        return [v for v in self.vehicles if not v.is_terminated]

    @with_authorization_policy(
        company_admin_at, get_target_from_args=lambda self, info: self
    )
    def resolve_employments(self, info):
        return [e for e in self.employments if e.is_not_rejected]


from app.data_access.user import UserOutput
