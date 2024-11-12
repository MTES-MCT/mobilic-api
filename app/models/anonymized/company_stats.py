from app import db
from .base import AnonymizedModel


class CompanyStatsAnonymized(AnonymizedModel):
    __tablename__ = "company_stats_anonymized"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, nullable=False)
    creation_time = db.Column(db.DateTime, nullable=False)
    company_creation_date = db.Column(db.Date, nullable=False)
    first_employee_invitation_date = db.Column(db.Date, nullable=True)
    first_mission_validation_by_admin_date = db.Column(db.Date, nullable=True)
    first_active_criteria_date = db.Column(db.Date, nullable=True)
    first_certification_date = db.Column(db.Date, nullable=True)

    @classmethod
    def anonymize(cls, stats):
        anonymized = cls()
        anonymized.id = cls.get_new_id("company_stats", stats.id)
        anonymized.company_id = cls.get_new_id("company", stats.company_id)
        anonymized.creation_time = cls.truncate_to_month(stats.creation_time)
        anonymized.company_creation_date = cls.truncate_to_month(
            stats.company_creation_date
        )
        if stats.first_employee_invitation_date:
            anonymized.first_employee_invitation_date = cls.truncate_to_month(
                stats.first_employee_invitation_date
            )
        if stats.first_mission_validation_by_admin_date:
            anonymized.first_mission_validation_by_admin_date = (
                cls.truncate_to_month(
                    stats.first_mission_validation_by_admin_date
                )
            )
        if stats.first_active_criteria_date:
            anonymized.first_active_criteria_date = cls.truncate_to_month(
                stats.first_active_criteria_date
            )
        if stats.first_certification_date:
            anonymized.first_certification_date = cls.truncate_to_month(
                stats.first_certification_date
            )
        return anonymized
