import graphene
from flask import g

from app.domain.permissions import is_employed_by_company_over_period
from app.helpers.authorization import with_authorization_policy
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.company_known_address import CompanyKnownAddressOutput
from app.models.team import Team
from app.models.vehicle import VehicleOutput


class TeamOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Team
        only_fields = (
            "name",
            "vehicles",
            "known_addresses",
            "creation_time",
            "admin_users",
        )

    creation_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )

    vehicles = graphene.List(
        VehicleOutput, description="Liste des véhicules de l'équipe"
    )

    known_addresses = graphene.List(
        CompanyKnownAddressOutput,
        description="Liste des lieux enregistrés de l'équipe'",
    )

    users = graphene.List(
        lambda: UserOutput,
        description="Liste des salariés affectés à l'équipe'",
    )

    @with_authorization_policy(
        is_employed_by_company_over_period,
        get_target_from_args=lambda self, info, **kwargs: self.company,
        error_message="Forbidden access to field 'vehicles' of team object.",
    )
    def resolve_vehicles(self, info):
        return [v for v in self.vehicles if not v.is_terminated]

    @with_authorization_policy(
        is_employed_by_company_over_period,
        get_target_from_args=lambda self, info, **kwargs: self.company,
        error_message="Forbidden access to field 'known_addresses' of team object.",
    )
    def resolve_known_addresses(self, info):
        return [a for a in self.known_addresses if not a.is_dismissed]

    @with_authorization_policy(
        is_employed_by_company_over_period,
        get_target_from_args=lambda self, info, **kwargs: self.company,
        error_message="Forbidden access to field 'users' of team object.",
    )
    def resolve_users(self, info):
        user_ids = [
            e.user_id for e in self.employments if e.user_id is not None
        ]
        users = g.dataloaders["users"].load_many(user_ids)
        return users

    @with_authorization_policy(
        is_employed_by_company_over_period,
        get_target_from_args=lambda self, info, **kwargs: self.company,
        error_message="Forbidden access to field 'admin_users' of team object.",
    )
    def resolve_admin_users(self, info):
        return self.admin_users


from app.data_access.user import UserOutput
