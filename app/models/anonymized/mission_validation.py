from app import db
from .base import AnonymizedModel


class MissionValidationAnonymized(AnonymizedModel):
    __tablename__ = "mission_validation_anonymized"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    reception_time = db.Column(db.DateTime, nullable=False)
    mission_id = db.Column(db.Integer, nullable=False)
    submitter_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=True)
    is_admin = db.Column(db.Boolean, nullable=False)

    @classmethod
    def anonymize(cls, validation):
        anonymized = cls()
        anonymized.id = cls.get_new_id("mission_validation", validation.id)
        anonymized.mission_id = cls.get_new_id(
            "mission", validation.mission_id
        )
        anonymized.submitter_id = cls.get_new_id(
            "user", validation.submitter_id
        )
        anonymized.user_id = (
            cls.get_new_id("user", validation.user_id)
            if validation.user_id
            else None
        )
        anonymized.is_admin = validation.is_admin
        anonymized.creation_time = cls.truncate_to_month(
            validation.creation_time
        )
        anonymized.reception_time = cls.truncate_to_month(
            validation.reception_time
        )

        return anonymized
