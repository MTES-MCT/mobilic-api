from enum import IntEnum

from sqlalchemy.orm import backref

from app import db
from app.models.base import BaseModel


class CertificationLevel(IntEnum):
    NO_CERTIFICATION = 0
    BRONZE = 1
    SILVER = 2
    GOLD = 3
    DIAMOND = 4


class CompanyCertification(BaseModel):
    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref=backref("certifications_new"))

    attribution_date = db.Column(db.Date, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    log_in_real_time = db.Column(db.Float, default=0.0, nullable=False)
    admin_changes = db.Column(db.Float, default=0.0, nullable=False)
    compliancy = db.Column(db.Integer, default=0, nullable=False)

    @property
    def certification_level(self):
        return CertificationLevel.NO_CERTIFICATION
