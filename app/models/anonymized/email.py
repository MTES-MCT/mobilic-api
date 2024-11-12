from app import db
from .base import AnonymizedModel


class EmailAnonymized(AnonymizedModel):
    __tablename__ = "email_anonymized"
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    type = db.Column(db.String(34), nullable=False)
    user_id = db.Column(db.Integer, nullable=True)
    employment_id = db.Column(db.Integer, nullable=True)

    @classmethod
    def anonymize(cls, email):
        """handle legacy and usual case""" ""
        anonymized = cls()

        if hasattr(email, "_mapping"):
            data = email._mapping
            anonymized.id = cls.get_new_id("email", data["id"])
            anonymized.creation_time = cls.truncate_to_month(
                data["creation_time"]
            )
            anonymized.type = "legacy_email"
            anonymized.user_id = (
                cls.get_new_id("user", data["user_id"])
                if data["user_id"]
                else None
            )
            anonymized.employment_id = (
                cls.get_new_id("employment", data["employment_id"])
                if data["employment_id"]
                else None
            )
        if not hasattr(email, "_mapping"):
            anonymized.id = cls.get_new_id("email", email.id)
            anonymized.creation_time = cls.truncate_to_month(
                email.creation_time
            )
            anonymized.type = email.type
            anonymized.user_id = (
                cls.get_new_id("user", email.user_id)
                if email.user_id
                else None
            )
            anonymized.employment_id = (
                cls.get_new_id("employment", email.employment_id)
                if email.employment_id
                else None
            )

        return anonymized
