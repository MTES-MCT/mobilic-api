from app import db
from .base import AnonymizedModel


class VehicleAnonymized(AnonymizedModel):
    __tablename__ = "vehicle_anonymized"

    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, nullable=False)
    terminated_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def anonymize(cls, vehicle):
        anonymized = cls()
        anonymized.id = cls.get_new_id("vehicle", vehicle.id)
        anonymized.submitter_id = cls.get_new_id("user", vehicle.submitter_id)
        if vehicle.terminated_at:
            anonymized.terminated_at = cls.truncate_to_month(
                vehicle.terminated_at
            )
        return anonymized