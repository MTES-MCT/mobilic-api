from enum import IntEnum

from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import backref

from app import db
from app.models.base import BaseModel

# Every month a certification level is computed for every eligible companies
# Depending on the results, a company can have a bronze/silver/gold/diamond certification medal
# A company is certified if it has at least bronze level
# A certification is valid for N(2) months
# At a certain point in time, a company has the best certification level still valid
# Certification is based on 3 criteria:
#
# Admin Changes: % of activities modified by admins (lower = better)
# Log in real time: % of activities logged within 60 minutes (log time versus start time) (higher = better)
# Compliancy: score from 0 to 6 (for each regulation checks). A regulation check is validated if # of alerts is < 0.5% of # of activities (higher = better)


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
    certification_level_int = db.Column(
        "certification_level", db.Integer, nullable=False
    )

    def get_certification_level(self):

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
    def certification_level(self) -> CertificationLevel:
        if self.certification_level_int is None:
            return self.get_certification_level()
        return CertificationLevel(self.certification_level_int)

    @certification_level.setter
    def certification_level(self, value: CertificationLevel):
        self.certification_level_int = int(value)

    @property
    def certified(self):
        return self.certification_level >= CertificationLevel.BRONZE


@event.listens_for(CompanyCertification, "before_insert")
@event.listens_for(CompanyCertification, "before_update")
def set_certification(
    mapper, connection, company_certification: CompanyCertification
):
    company_certification.certification_level = (
        company_certification.get_certification_level()
    )
