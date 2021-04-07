from sqlalchemy.dialects.postgresql import JSONB
import graphene

from app.helpers.errors import InvalidParamsError
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.base import BaseModel
from app import db


class Address(BaseModel):
    geo_api_id = db.Column(db.String(255), nullable=True, index=True)
    type = db.Column(db.String(20), nullable=True)
    coords = db.Column(db.ARRAY(db.Numeric), nullable=True)
    postal_code = db.Column(db.String(20), nullable=True)
    city = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    geo_api_raw_data = db.Column(JSONB(none_as_null=True), nullable=True)
    manual = db.Column(db.Boolean, nullable=False)

    @classmethod
    def get_or_create(cls, data):
        try:
            geo_api_id = data["properties"]["id"]
            properties = dict(
                type=data["properties"]["type"],
                postal_code=data["properties"]["postcode"],
                city=data["properties"]["city"],
                name=data["properties"]["name"],
                coords=data["geometry"]["coordinates"],
            )
        except:
            raise InvalidParamsError("Could not parse GeoJSON payload")
        existing_addresses = cls.query.filter(
            cls.geo_api_id == geo_api_id
        ).all()
        for addr in existing_addresses:
            are_addresses_equal = True
            for key, value in properties.items():
                if value != getattr(addr, key):
                    are_addresses_equal = False
                    break
            if are_addresses_equal:
                return addr
        address = cls(
            **properties,
            geo_api_id=geo_api_id,
            geo_api_raw_data=data,
            manual=False,
        )
        db.session.add(address)
        return address

    def format(self):
        if self.manual:
            return self.name
        return f"{self.name} {self.postal_code} {self.city}"


class BaseAddressOutput(graphene.Interface):
    name = graphene.Field(
        graphene.String,
        required=True,
        description="Libellé de l'adresse ou du lieu",
    )
    city = graphene.Field(
        graphene.String,
        required=False,
        description="Commune de l'adresse ou du lieu",
    )
    postal_code = graphene.Field(
        graphene.String,
        required=False,
        description="Code postal de l'adresse ou du lieu",
    )
    alias = graphene.Field(
        graphene.String,
        required=False,
        description="Alias de l'adresse ou du lieu",
    )

    @classmethod
    def resolve_type(cls, instance, info):
        from app.models.company_known_address import CompanyKnownAddressOutput

        if hasattr(instance, "type"):
            return AddressOutput
        return CompanyKnownAddressOutput


class AddressOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Address
        interfaces = (BaseAddressOutput,)
        only_fields = ("name", "postal_code", "city")

    def resolve_alias(self, info):
        return None
