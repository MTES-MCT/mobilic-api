from app import db
from .base import AnonymizedModel


class AnonUserAgreement(AnonymizedModel):
    __tablename__ = "anon_user_agreement"
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(length=50), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_blacklisted = db.Column(db.Boolean, nullable=False)

    @classmethod
    def anonymize(cls, agreement):
        new_id = cls.get_new_id("user_agreement", agreement.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.creation_time = cls.truncate_to_month(
            agreement.creation_time
        )
        anonymized.user_id = cls.get_new_id("user", agreement.user_id)
        anonymized.status = agreement.status
        anonymized.expires_at = cls.truncate_to_month(agreement.expires_at)
        anonymized.is_blacklisted = agreement.is_blacklisted
        return anonymized
