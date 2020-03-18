import graphene

from app.data_access.user import UserOutput
from app.domain.permissions import belongs_to_company
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models import Company


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
