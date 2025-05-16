from app import db
from .base import AnonymizedModel


class AnonEmail(AnonymizedModel):
    __tablename__ = "anon_email"
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    type = db.Column(db.String(34), nullable=False)
    user_id = db.Column(db.Integer, nullable=True)
    employment_id = db.Column(db.Integer, nullable=True)

    @classmethod
    def anonymize(cls, email):
        """handle legacy and usual case"""
        if hasattr(email, "_mapping"):
            data = email._mapping
            new_id = cls.get_new_id("email", data["id"])
        else:
            new_id = cls.get_new_id("email", email.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()

        if hasattr(email, "_mapping"):
            data = email._mapping
            anonymized.id = new_id
            anonymized.creation_time = cls.truncate_to_month(
                data["creation_time"]
            )
            anonymized.type = "legacy_email"
            anonymized.user_id = cls.get_new_id("user", data["user_id"])
            anonymized.employment_id = cls.get_new_id(
                "employment", data["employment_id"]
            )
        else:
            anonymized.id = new_id
            anonymized.creation_time = cls.truncate_to_month(
                email.creation_time
            )
            anonymized.type = email.type
            anonymized.user_id = cls.get_new_id("user", email.user_id)
            anonymized.employment_id = cls.get_new_id(
                "employment", email.employment_id
            )

        return anonymized
