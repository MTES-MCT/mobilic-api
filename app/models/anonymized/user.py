from app import db
from .base import AnonymizedModel
from app.models.utils import enum_column
from app.models.user import UserAccountStatus


class UserAnonymized(AnonymizedModel):
    __tablename__ = "user_anonymized"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    admin = db.Column(db.Boolean, default=False, nullable=False)
    has_confirmed_email = db.Column(db.Boolean, default=False, nullable=False)
    has_activated_email = db.Column(db.Boolean, default=False, nullable=False)
    way_heard_of_mobilic = db.Column(db.String(255), nullable=True)
    status = enum_column(UserAccountStatus, nullable=False)

    @classmethod
    def anonymize(cls, user):
        anonymized = cls()
        anonymized.id = cls.get_new_id("user", user.id)
        anonymized.creation_time = cls.truncate_to_month(user.creation_time)
        anonymized.admin = user.admin
        anonymized.has_confirmed_email = user.has_confirmed_email
        anonymized.has_activated_email = user.has_activated_email
        anonymized.way_heard_of_mobilic = user.way_heard_of_mobilic
        anonymized.status = user.status

        return anonymized
