from datetime import datetime, date
from sqlalchemy import or_

from app import db
from app.models import Employment
from app.models.employment import EmploymentRequestValidationStatus


def create_employment_by_third_party_if_needed(
    user_id, company_id, email, has_admin_rights
):
    current_date = datetime.utcnow().date()
    existing_employment = Employment.query.filter(
        Employment.user_id == user_id,
        Employment.company_id == company_id,
        ~Employment.is_dismissed,
        Employment.end_date.is_(None),
        or_(
            Employment.end_date.is_(None), Employment.end_date == current_date
        ),
    ).one_or_none()

    if existing_employment:
        existing_employment.has_admin_rights = has_admin_rights
        return existing_employment, False

    employment = Employment(
        user_id=user_id,
        submitter_id=user_id,
        company_id=company_id,
        reception_time=datetime.now(),
        start_date=date.today(),
        has_admin_rights=has_admin_rights,
        email=email,
        validation_status=EmploymentRequestValidationStatus.PENDING,
    )
    db.session.add(employment)
    db.session.flush()

    return employment, True


def validate_employment(employment):
    if (
        employment.validation_status
        != EmploymentRequestValidationStatus.APPROVED
    ):
        employment.validation_status = (
            EmploymentRequestValidationStatus.APPROVED
        )
        employment.validation_time = datetime.now()
