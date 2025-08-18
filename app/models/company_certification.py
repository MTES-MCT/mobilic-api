from enum import IntEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref

from app import db
from app.models.base import BaseModel


class CertificationLevel(IntEnum):
    NO_CERTIFICATION = 0
    BRONZE = 1
    SILVER = 2
    GOLD = 3
    DIAMOND = 4


CERTIFICATION_ADMIN_CHANGES_BRONZE = 0.3
CERTIFICATION_ADMIN_CHANGES_SILVER = 0.2
CERTIFICATION_ADMIN_CHANGES_GOLD = 0.1
CERTIFICATION_ADMIN_CHANGES_DIAMOND = 0.01

CERTIFICATION_REAL_TIME_BRONZE = 0.6
CERTIFICATION_REAL_TIME_SILVER = 0.7
CERTIFICATION_REAL_TIME_GOLD = 0.8
CERTIFICATION_REAL_TIME_DIAMOND = 0.95

CERTIFICATION_COMPLIANCY_SILVER = 2
CERTIFICATION_COMPLIANCY_GOLD = 4
CERTIFICATION_COMPLIANCY_DIAMOND = 6


class CompanyCertification(BaseModel):
    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref=backref("certifications"))

    attribution_date = db.Column(db.Date, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    log_in_real_time = db.Column(db.Float, default=0.0, nullable=False)
    admin_changes = db.Column(db.Float, default=0.0, nullable=False)
    compliancy = db.Column(db.Integer, default=0, nullable=False)
    info = db.Column(JSONB(none_as_null=True), nullable=True)

    @property
    def certification_medal(self):

        if (
            self.compliancy >= CERTIFICATION_COMPLIANCY_DIAMOND
            and self.log_in_real_time >= CERTIFICATION_REAL_TIME_DIAMOND
            and self.admin_changes <= CERTIFICATION_ADMIN_CHANGES_DIAMOND
        ):
            return CertificationLevel.DIAMOND

        if (
            self.compliancy >= CERTIFICATION_COMPLIANCY_GOLD
            and self.log_in_real_time >= CERTIFICATION_REAL_TIME_GOLD
            and self.admin_changes <= CERTIFICATION_ADMIN_CHANGES_GOLD
        ):
            return CertificationLevel.GOLD

        if (
            self.compliancy >= CERTIFICATION_COMPLIANCY_SILVER
            and self.log_in_real_time >= CERTIFICATION_REAL_TIME_SILVER
            and self.admin_changes <= CERTIFICATION_ADMIN_CHANGES_SILVER
        ):
            return CertificationLevel.SILVER

        if (
            self.log_in_real_time >= CERTIFICATION_REAL_TIME_BRONZE
            and self.admin_changes <= CERTIFICATION_ADMIN_CHANGES_BRONZE
        ):
            return CertificationLevel.BRONZE

        return CertificationLevel.NO_CERTIFICATION

    @property
    def certified(self):
        return self.certification_medal >= CertificationLevel.BRONZE
