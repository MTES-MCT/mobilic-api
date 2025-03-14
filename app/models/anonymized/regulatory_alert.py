from app import db
from .base import AnonymizedModel


class AnonRegulatoryAlert(AnonymizedModel):
    __tablename__ = "anon_regulatory_alert"
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    day = db.Column(db.Date, nullable=False)
    extra = db.Column(db.JSON, nullable=True)
    submitter_type = db.Column(db.String(length=50), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    regulation_check_id = db.Column(db.Integer, nullable=False)

    @classmethod
    def anonymize(cls, alert):
        anonymized = cls()
        anonymized.id = cls.get_new_id("regulatory_alert", alert.id)
        anonymized.creation_time = cls.truncate_to_month(alert.creation_time)
        anonymized.day = cls.truncate_to_month(alert.day)
        anonymized.extra = alert.extra
        anonymized.submitter_type = alert.submitter_type
        anonymized.user_id = cls.get_new_id("user", alert.user_id)
        anonymized.regulation_check_id = alert.regulation_check_id
        return anonymized
