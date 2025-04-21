from app import db
from .base import AnonymizedModel


class AnonVehicle(AnonymizedModel):
    __tablename__ = "anon_vehicle"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    submitter_id = db.Column(db.Integer, nullable=False)
    terminated_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def anonymize(cls, vehicle):
        new_id = cls.get_new_id("vehicle", vehicle.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.company_id = cls.get_new_id("company", vehicle.company_id)
        anonymized.submitter_id = cls.get_new_id("user", vehicle.submitter_id)
        if vehicle.terminated_at:
            anonymized.terminated_at = cls.truncate_to_month(
                vehicle.terminated_at
            )
        return anonymized
