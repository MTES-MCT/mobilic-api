from sqlalchemy.orm import backref
import graphene

from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.address import BaseAddressOutput
from app.models.base import BaseModel
from app import db
from app.models.event import Dismissable


class CompanyKnownAddress(BaseModel, Dismissable):
    address_id = db.Column(
        db.Integer, db.ForeignKey("address.id"), index=True, nullable=False
    )
    address = db.relationship("Address")

    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref=backref("known_addresses"))

    alias = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "address_id",
            name="only_one_entry_per_company_and_address",
        ),
    )

    def format(self):
        return self.address.format()


class CompanyKnownAddressOutput(BaseSQLAlchemyObjectType):
    class Meta:
        interfaces = (BaseAddressOutput,)
        model = CompanyKnownAddress
        only_fields = ("alias", "id")

    id = graphene.Field(graphene.Int, required=True)

    def resolve_name(self, info):
        return self.address.name

    def resolve_postal_code(self, info):
        return self.address.postal_code

    def resolve_city(self, info):
        return self.address.city
