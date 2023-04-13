from sqlalchemy.orm import backref

from app import db
from app.models.base import BaseModel


class CompanyCertification(BaseModel):
    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref=backref("certifications"))

    attribution_date = db.Column(db.Date, nullable=False)
    expiration_date = db.Column(db.Date, nullable=True)
    be_active = db.Column(db.Boolean, default=False, nullable=False)
    be_compliant = db.Column(db.Boolean, default=False, nullable=False)
    not_too_many_changes = db.Column(db.Boolean, default=False, nullable=False)
    validate_regularly = db.Column(db.Boolean, default=False, nullable=False)
    log_in_real_time = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def certified(self):
        return (
            self.be_active
            and self.be_compliant
            and self.not_too_many_changes
            and self.validate_regularly
            and self.log_in_real_time
        )
