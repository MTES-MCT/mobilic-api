from app import db
from .base import AnonymizedModel


class AnonCompanyCertification(AnonymizedModel):
    __tablename__ = "anon_company_certification"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    creation_time = db.Column(db.DateTime, nullable=False)
    attribution_date = db.Column(db.Date, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    be_active = db.Column(db.Boolean, nullable=False)
    be_compliant = db.Column(db.Boolean, nullable=False)
    not_too_many_changes = db.Column(db.Boolean, nullable=False)
    validate_regularly = db.Column(db.Boolean, nullable=False)
    log_in_real_time = db.Column(db.Boolean, nullable=False)

    @classmethod
    def anonymize(cls, cert):
        anonymized = cls()
        anonymized.id = cls.get_new_id("company_certification", cert.id)
        anonymized.company_id = cls.get_new_id("company", cert.company_id)
        anonymized.creation_time = cls.truncate_to_month(cert.creation_time)
        anonymized.attribution_date = cls.truncate_to_month(
            cert.attribution_date
        )
        anonymized.expiration_date = cls.truncate_to_month(
            cert.expiration_date
        )
        anonymized.be_active = cert.be_active
        anonymized.be_compliant = cert.be_compliant
        anonymized.not_too_many_changes = cert.not_too_many_changes
        anonymized.validate_regularly = cert.validate_regularly
        anonymized.log_in_real_time = cert.log_in_real_time
        return anonymized
