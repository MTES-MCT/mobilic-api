from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, func, or_

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
    """Ended missions validated by at least one worker but not yet by admin.

    A mission requires admin action only once a worker has confirmed it;
    counting ended-but-not-yet-worker-validated missions would mismatch the
    Validations panel.
    """
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

    worker_validated_ids = (
        db.session.query(MissionValidation.mission_id)
        .filter(
            MissionValidation.is_admin.is_(False),
        )
        .distinct()
    )

    admin_validated_ids = db.session.query(
        MissionValidation.mission_id
    ).filter(
        MissionValidation.is_admin.is_(True),
    )

    return (
        db.session.query(func.count(ended_missions.c.id))
        .filter(ended_missions.c.id.in_(worker_validated_ids))
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
    """Approved non-admin employees active in the last 30 days but not today.

    Matches the InactiveEmployeesDropdown logic in the frontend, which only
    surfaces employees who have used Mobilic recently (so freshly-onboarded
    or long-gone employees do not pollute the count).
    """
    today_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    threshold_30_days = today_start - timedelta(days=30)

    return (
        db.session.query(func.count(func.distinct(Employment.user_id)))
        .filter(
            Employment.company_id == company_id,
            Employment.validation_status
            == EmploymentRequestValidationStatus.APPROVED,
            ~Employment.is_dismissed,
            Employment.has_admin_rights.is_(False),
            Employment.user_id.isnot(None),
            Employment.last_active_at.isnot(None),
            Employment.last_active_at >= threshold_30_days,
            Employment.last_active_at < today_start,
            or_(
                Employment.end_date.is_(None),
                Employment.end_date >= date.today(),
            ),
        )
        .scalar()
    ) or 0


def _has_any_mission_this_week(company_id):
    """True if the company has at least one non-dismissed activity since Monday."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    week_start = datetime.combine(monday, time.min, tzinfo=timezone.utc)
    return db.session.query(
        db.session.query(Activity.id)
        .join(Mission, Activity.mission_id == Mission.id)
        .filter(
            Mission.company_id == company_id,
            ~Activity.is_dismissed,
            Activity.start_time >= week_start,
        )
        .exists()
    ).scalar()


def _count_auto_validated_missions(company_id):
    """Missions auto-validated by the system today.

    Limited to today's validations so the counter reflects the
    end-of-day batch the manager can still react to.
    """
    today_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
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
            MissionValidation.creation_time >= today_start,
            MissionValidation.creation_time < today_end,
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
        has_any_mission_this_week=_has_any_mission_this_week(company_id),
    )
