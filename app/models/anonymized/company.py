from app import db
from .base import AnonymizedModel


class AnonCompany(AnonymizedModel):
    __tablename__ = "anon_company"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    require_kilometer_data = db.Column(db.Boolean, nullable=False)
    business_id = db.Column(db.Integer, nullable=True)

    @classmethod
    def anonymize(cls, company):
        new_id = cls.get_new_id("company", company.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.creation_time = cls.truncate_to_month(company.creation_time)
        anonymized.require_kilometer_data = company.require_kilometer_data
        anonymized.business_id = company.business_id

        return anonymized
