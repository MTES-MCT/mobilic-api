from app import db
from .base import AnonymizedModel


class AnonCompanyStats(AnonymizedModel):
    __tablename__ = "anon_company_stats"

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
        new_id = cls.get_new_id("company_stats", stats.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.company_id = cls.get_new_id("company", stats.company_id)
        anonymized.creation_time = cls.truncate_to_month(stats.creation_time)
        anonymized.company_creation_date = cls.truncate_to_month(
            stats.company_creation_date
        )

        if stats.first_employee_invitation_date:
            time_diff = (
                stats.first_employee_invitation_date
                - stats.company_creation_date
            )
            anonymized.first_employee_invitation_date = (
                anonymized.company_creation_date + time_diff
            )

        if stats.first_mission_validation_by_admin_date:
            time_diff = (
                stats.first_mission_validation_by_admin_date
                - stats.company_creation_date
            )
            anonymized.first_mission_validation_by_admin_date = (
                anonymized.company_creation_date + time_diff
            )

        if stats.first_active_criteria_date:
            time_diff = (
                stats.first_active_criteria_date - stats.company_creation_date
            )
            anonymized.first_active_criteria_date = (
                anonymized.company_creation_date + time_diff
            )

        if stats.first_certification_date:
            time_diff = (
                stats.first_certification_date - stats.company_creation_date
            )
            anonymized.first_certification_date = (
                anonymized.company_creation_date + time_diff
            )

        return anonymized
