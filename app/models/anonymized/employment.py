from app import db
from .base import AnonymizedModel


class AnonEmployment(AnonymizedModel):
    __tablename__ = "anon_employment"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    validation_time = db.Column(db.DateTime, nullable=True)
    validation_status = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    company_id = db.Column(db.Integer, nullable=False)
    has_admin_rights = db.Column(db.Boolean, nullable=True)
    user_id = db.Column(db.Integer, nullable=True)
    submitter_id = db.Column(db.Integer, nullable=False)
    team_id = db.Column(db.Integer, nullable=True)
    business_id = db.Column(db.Integer, nullable=True)

    @classmethod
    def anonymize(cls, employment):
        new_id = cls.get_new_id("employment", employment.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.company_id = cls.get_new_id(
            "company", employment.company_id
        )
        anonymized.user_id = cls.get_new_id("user", employment.user_id)
        anonymized.submitter_id = cls.get_new_id(
            "user", employment.submitter_id
        )
        anonymized.team_id = cls.get_new_id("team", employment.team_id)
        anonymized.business_id = cls.get_new_id(
            "business", employment.business_id
        )
        anonymized.creation_time = cls.truncate_to_month(
            employment.creation_time
        )
        anonymized.validation_time = cls.truncate_to_month(
            employment.validation_time
        )
        anonymized.validation_status = employment.validation_status
        anonymized.start_date = cls.truncate_to_month(employment.start_date)
        anonymized.end_date = cls.truncate_to_month(employment.end_date)
        anonymized.has_admin_rights = employment.has_admin_rights

        return anonymized
