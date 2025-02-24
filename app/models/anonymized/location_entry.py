from app import db
from .base import AnonymizedModel


class LocationEntryAnonymized(AnonymizedModel):
    __tablename__ = "anon_location_entry"

    id = db.Column(db.Integer, primary_key=True)
    submitter_id = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(22), nullable=False)
    creation_time = db.Column(db.DateTime, nullable=False)
    mission_id = db.Column(db.Integer, nullable=False)
    address_id = db.Column(db.Integer, nullable=False)
    company_known_address_id = db.Column(db.Integer, nullable=True)

    @classmethod
    def anonymize(cls, location):
        anonymized = cls()
        anonymized.id = cls.get_new_id("location_entry", location.id)
        anonymized.submitter_id = cls.get_new_id("user", location.submitter_id)
        anonymized.type = location.type
        anonymized.creation_time = cls.truncate_to_month(
            location.creation_time
        )
        anonymized.mission_id = cls.get_new_id("mission", location.mission_id)
        anonymized.address_id = cls.get_new_id("address", location.address_id)
        anonymized.company_known_address_id = cls.get_new_id(
            "company_known_address", location.company_known_address_id
        )

        return anonymized
