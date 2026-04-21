from datetime import date, datetime, time, timezone

from sqlalchemy import and_, func

from app import db
from app.data_access.dashboard_summary import DashboardSummary
from app.models import (
    Activity,
    Employment,
    Mission,
    MissionEnd,
    MissionValidation,
)
from app.models.employment import EmploymentRequestValidationStatus


def _count_active_missions(company_id):
    """Missions where at least one user hasn't ended."""
    return (
        db.session.query(func.count(func.distinct(Activity.mission_id)))
        .join(Mission, Activity.mission_id == Mission.id)
        .outerjoin(
            MissionEnd,
            and_(
                MissionEnd.mission_id == Activity.mission_id,
                MissionEnd.user_id == Activity.user_id,
            ),
        )
        .filter(
            Mission.company_id == company_id,
            ~Activity.is_dismissed,
            MissionEnd.id.is_(None),
        )
        .scalar()
    ) or 0


def _count_pending_validations(company_id):
    """Ended missions without admin validation."""
    ended_missions = (
        db.session.query(Mission.id)
        .join(Activity, Activity.mission_id == Mission.id)
        .outerjoin(
            MissionEnd,
            and_(
                MissionEnd.mission_id == Mission.id,
                MissionEnd.user_id == Activity.user_id,
            ),
        )
        .filter(
            Mission.company_id == company_id,
            ~Activity.is_dismissed,
        )
        .group_by(Mission.id)
        .having(func.every(MissionEnd.id.isnot(None)))
        .subquery()
    )

    admin_validated_ids = db.session.query(
        MissionValidation.mission_id
    ).filter(
        MissionValidation.is_admin.is_(True),
        MissionValidation.user_id.is_(None),
    )

    return (
        db.session.query(func.count(ended_missions.c.id))
        .filter(ended_missions.c.id.notin_(admin_validated_ids))
        .scalar()
    ) or 0


def _get_pending_invitations(company_id):
    """Employments with pending status and no linked user."""
    pending = (
        db.session.query(Employment.id)
        .filter(
            Employment.company_id == company_id,
            Employment.validation_status
            == EmploymentRequestValidationStatus.PENDING,
            Employment.user_id.is_(None),
            ~Employment.is_dismissed,
        )
        .all()
    )
    return [row.id for row in pending]


def _count_inactive_employees(company_id):
    """Approved employees with no activity today."""
    today_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)

    active_user_ids = (
        db.session.query(func.distinct(Activity.user_id))
        .join(Mission, Activity.mission_id == Mission.id)
        .filter(
            Mission.company_id == company_id,
            ~Activity.is_dismissed,
            Activity.start_time >= today_start,
        )
        .subquery()
    )

    return (
        db.session.query(func.count(Employment.id))
        .filter(
            Employment.company_id == company_id,
            Employment.validation_status
            == EmploymentRequestValidationStatus.APPROVED,
            ~Employment.is_dismissed,
            Employment.has_admin_rights.is_(False),
            Employment.user_id.isnot(None),
            Employment.user_id.notin_(db.session.query(active_user_ids)),
        )
        .scalar()
    ) or 0


def _count_auto_validated_missions(company_id):
    """Missions auto-validated by the system (admin)."""
    return (
        db.session.query(
            func.count(func.distinct(MissionValidation.mission_id))
        )
        .join(
            Mission,
            MissionValidation.mission_id == Mission.id,
        )
        .filter(
            Mission.company_id == company_id,
            MissionValidation.is_admin.is_(True),
            MissionValidation.is_auto.is_(True),
            MissionValidation.user_id.is_(None),
        )
        .scalar()
    ) or 0


def get_dashboard_summary(company_id):
    pending_ids = _get_pending_invitations(company_id)
    return DashboardSummary(
        active_missions_count=_count_active_missions(company_id),
        pending_validations_count=_count_pending_validations(company_id),
        pending_invitations_count=len(pending_ids),
        pending_invitation_employment_ids=pending_ids,
        inactive_employees_count=_count_inactive_employees(company_id),
        auto_validated_missions_count=(
            _count_auto_validated_missions(company_id)
        ),
    )
