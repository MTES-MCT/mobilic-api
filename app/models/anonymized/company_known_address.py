from app import db
from .base import AnonymizedModel


class AnonCompanyKnownAddress(AnonymizedModel):
    __tablename__ = "anon_company_known_address"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    creation_time = db.Column(db.DateTime, nullable=False)
    address_id = db.Column(db.Integer, nullable=False)

    @classmethod
    def anonymize(cls, address):
        anonymized = cls()
        anonymized.id = cls.get_new_id("company_known_address", address.id)
        anonymized.company_id = cls.get_new_id("company", address.company_id)
        anonymized.creation_time = cls.truncate_to_month(address.creation_time)
        anonymized.address_id = cls.get_new_id("address", address.address_id)
        return anonymized
