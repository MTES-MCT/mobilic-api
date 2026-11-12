from datetime import datetime, date, timezone
from sqlalchemy import or_, func

from app import db
from app.models import Employment
from app.models.employment import EmploymentRequestValidationStatus


def get_already_invited_emails(company_id, emails):
    """Lowercased emails that already have an outstanding email invitation in the
    company (pending or active, not rejected/dismissed/terminated).

    Email invitations have no user_id, so they escape the
    no_simultaneous_employments_for_the_same_company exclusion constraint and
    must be guarded here.
    """
    normalized = {email.lower() for email in emails if email}
    if not normalized:
        return set()
    today = datetime.now(timezone.utc).date()
    rows = (
        db.session.query(func.lower(Employment.email))
        .filter(
            Employment.company_id == company_id,
            Employment.user_id.is_(None),
            func.lower(Employment.email).in_(normalized),
            Employment.validation_status
            != EmploymentRequestValidationStatus.REJECTED,
            ~Employment.is_dismissed,
            or_(
                Employment.end_date.is_(None),
                Employment.end_date >= today,
            ),
        )
        .all()
    )
    return {row[0] for row in rows}


def create_employment_by_third_party_if_needed(
    user_id, company_id, email, has_admin_rights
):
    current_date = datetime.now(timezone.utc).date()
    existing_employment = Employment.query.filter(
        Employment.user_id == user_id,
        Employment.company_id == company_id,
        ~Employment.is_dismissed,
        or_(
            Employment.end_date.is_(None), Employment.end_date >= current_date
        ),
    ).one_or_none()

    if existing_employment:
        existing_employment.has_admin_rights = has_admin_rights
        existing_employment.email = email
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
