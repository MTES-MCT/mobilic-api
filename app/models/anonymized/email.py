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
        anonymized = cls()
        anonymized.id = cls.get_new_id("email", email.id)
        anonymized.user_id = (
            cls.get_new_id("user", email.user_id) if email.user_id else None
        )
        anonymized.employment_id = (
            cls.get_new_id("employment", email.employment_id)
            if email.employment_id
            else None
        )
        anonymized.type = email.type
        anonymized.creation_time = cls.truncate_to_month(email.creation_time)

        return anonymized
