import graphene

from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.company_known_address import CompanyKnownAddressOutput
from app.models.team import Team
from app.models.vehicle import VehicleOutput


class TeamOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Team
        only_fields = ("name", "vehicles", "known_addresses", "creation_time")

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

    def resolve_vehicles(self, info):
        return [v for v in self.vehicles if not v.is_terminated]

    def resolve_known_addresses(self, info):
        return [a for a in self.known_addresses if not a.is_dismissed]
