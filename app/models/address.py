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
    def get_or_create(cls, geo_api_data=None, manual_address=None):
        if geo_api_data:
            try:
                geo_api_id = geo_api_data["properties"]["id"]
                properties = dict(
                    type=geo_api_data["properties"]["type"],
                    postal_code=geo_api_data["properties"]["postcode"],
                    city=geo_api_data["properties"]["city"],
                    name=geo_api_data["properties"]["name"],
                    coords=geo_api_data["geometry"]["coordinates"],
                    manual=False,
                )
                additional_props = dict(
                    geo_api_id=geo_api_id, geo_api_raw_data=geo_api_data
                )
            except:
                raise InvalidParamsError("Could not parse GeoJSON payload")
            existing_addresses = cls.query.filter(
                cls.geo_api_id == geo_api_id
            ).all()
        else:
            properties = dict(manual=True, name=manual_address)
            additional_props = dict()
            existing_addresses = cls.query.filter(
                cls.manual.is_(True), cls.name == manual_address
            )

        # We check whether the new address exists in the DB with the same exact properties.
        # If not or if at least one property differ we create a new DB entry.
        for addr in existing_addresses:
            are_addresses_equal = True
            for key, value in properties.items():
                if value != getattr(addr, key):
                    are_addresses_equal = False
                    break
            if are_addresses_equal:
                return addr

        address = cls(**properties, **additional_props)
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
        from app.models.location_entry import LocationEntry

        if hasattr(instance, "kilometer_reading"):
            return LocationEntry
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
