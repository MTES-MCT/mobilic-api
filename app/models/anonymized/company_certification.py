from app import db
from .base import AnonymizedModel


class AnonCompanyCertification(AnonymizedModel):
    __tablename__ = "anon_company_certification"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    creation_time = db.Column(db.DateTime, nullable=False)
    attribution_date = db.Column(db.Date, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    log_in_real_time = db.Column(db.Float, nullable=False)
    admin_changes = db.Column(db.Float, nullable=False)
    compliancy = db.Column(db.Integer, nullable=False)
    certification_level_int = db.Column(db.Integer, nullable=False)

    @classmethod
    def anonymize(cls, cert):
        new_id = cls.get_new_id("company_certification", cert.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.company_id = cls.get_new_id("company", cert.company_id)
        anonymized.creation_time = cls.truncate_to_month(cert.creation_time)
        anonymized.attribution_date = cls.truncate_to_month(
            cert.attribution_date
        )
        anonymized.expiration_date = cls.truncate_to_month(
            cert.expiration_date
        )
        anonymized.log_in_real_time = cert.log_in_real_time
        anonymized.admin_changes = cert.admin_changes
        anonymized.compliancy = cert.compliancy
        anonymized.certification_level_int = cert.certification_level_int
        return anonymized
