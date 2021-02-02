from sqlalchemy.orm import backref

from app.models.address import AddressOutput
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


class CompanyKnownAddressOutput(AddressOutput):
    class Meta:
        model = CompanyKnownAddress
        only_fields = ("alias", "id")

    def resolve_name(self, info):
        return self.address.name

    def resolve_postal_code(self, info):
        return self.address.postal_code

    def resolve_city(self, info):
        return self.address.city
