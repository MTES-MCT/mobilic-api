from app import db
from app.models.base import BaseModel


class CompanyStats(BaseModel):
    company_id = db.Column(
        db.Integer,
        db.ForeignKey("company.id"),
        index=True,
        unique=True,
        nullable=False,
    )
    company_creation_date = db.Column(db.Date, nullable=False)
    first_employee_invitation_date = db.Column(db.Date, nullable=True)
    first_mission_validation_by_admin_date = db.Column(db.Date, nullable=True)
    first_active_criteria_date = db.Column(db.Date, nullable=True)
    first_certification_date = db.Column(db.Date, nullable=True)
