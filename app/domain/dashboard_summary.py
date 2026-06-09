from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, or_

from app import db
from app.data_access.dashboard_summary import DashboardSummary
from app.helpers.time import from_tz
from app.models import (
    Activity,
    Employment,
    Mission,
    MissionEnd,
    MissionValidation,
)
from app.models.employment import EmploymentRequestValidationStatus


# Activities open for more than this many days are considered abnormal
# (worker forgot to close their chronometer). Bounding the window lets
# Postgres use the start_time range filter instead of scanning every
# Activity row of the company.
ACTIVE_MISSIONS_WINDOW_DAYS = 30

PENDING_VALIDATIONS_WINDOW_DAYS = 31


def _today_window_for_user(user_timezone):
    """Return (today_start, today_end) as UTC-naive datetimes where the day
    boundaries correspond to midnight in the manager's own timezone.

    Mobilic supports managers based in DOM-TOM, so the day boundary must
    follow the user's tz (not a hard-coded FR_TIMEZONE). All persisted
    timestamps (Activity.start_time, MissionValidation.creation_time,
    Employment.last_active_at) are stored as UTC-naive, so the returned
    boundaries can be compared directly.
    """
    today_local = datetime.now(tz=user_timezone).date()
    start_local_naive = datetime.combine(today_local, time.min)
    end_local_naive = datetime.combine(
        today_local + timedelta(days=1), time.min
    )
    return (
        from_tz(start_local_naive, user_timezone),
        from_tz(end_local_naive, user_timezone),
    )


def _week_start_for_user(user_timezone):
    today_local = datetime.now(tz=user_timezone).date()
    monday = today_local - timedelta(days=today_local.weekday())
    return from_tz(datetime.combine(monday, time.min), user_timezone)


def _count_active_missions(company_id):
    """Missions with at least one running activity (chronometer ticking).

    Bounded to the last ACTIVE_MISSIONS_WINDOW_DAYS days so Postgres can
    use the index on Activity.start_time instead of scanning the whole
    history of the company's activities. Any chronometer left open longer
    than this window is a data quality issue, not a normal "in progress"
    state.
    """
    cutoff = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(
        days=ACTIVE_MISSIONS_WINDOW_DAYS
    )
    return (
        db.session.query(func.count(func.distinct(Activity.mission_id)))
        .join(Mission, Activity.mission_id == Mission.id)
        .filter(
            Mission.company_id == company_id,
            ~Activity.is_dismissed,
            Activity.end_time.is_(None),
            Activity.start_time >= cutoff,
        )
        .scalar()
    ) or 0


def _count_pending_validations(company_id):
    """Missions started in the last PENDING_VALIDATIONS_WINDOW_DAYS days
    that are ended for every user, validated by at least one worker, and
    not yet validated by an admin.

    Implemented as correlated EXISTS/NOT EXISTS clauses driven by the
    company filter on Mission, so Postgres can short-circuit per row and
    never has to materialize a full scan of mission_validation /
    mission_end. Replaces a previous query that took >30 minutes in
    production.
    """
    window_start = datetime.now(tz=timezone.utc).replace(
        tzinfo=None
    ) - timedelta(days=PENDING_VALIDATIONS_WINDOW_DAYS)

    activity_in_window = (
        db.session.query(Activity.id)
        .filter(
            Activity.mission_id == Mission.id,
            ~Activity.is_dismissed,
            Activity.start_time >= window_start,
        )
        .exists()
    )

    activity_without_mission_end = (
        db.session.query(Activity.id)
        .filter(
            Activity.mission_id == Mission.id,
            ~Activity.is_dismissed,
            ~(
                db.session.query(MissionEnd.id)
                .filter(
                    MissionEnd.mission_id == Mission.id,
                    MissionEnd.user_id == Activity.user_id,
                )
                .exists()
            ),
        )
        .exists()
    )

    has_worker_validation = (
        db.session.query(MissionValidation.id)
        .filter(
            MissionValidation.mission_id == Mission.id,
            MissionValidation.is_admin.is_(False),
        )
        .exists()
    )

    has_admin_validation = (
        db.session.query(MissionValidation.id)
        .filter(
            MissionValidation.mission_id == Mission.id,
            MissionValidation.is_admin.is_(True),
        )
        .exists()
    )

    return (
        db.session.query(func.count(Mission.id))
        .filter(
            Mission.company_id == company_id,
            activity_in_window,
            ~activity_without_mission_end,
            has_worker_validation,
            ~has_admin_validation,
        )
        .scalar()
    ) or 0


def _get_pending_invitations(company_id):
    """Employments in pending status (not dismissed), whether they target
    a fresh email or an already-registered Mobilic user."""
    pending = (
        db.session.query(Employment.id)
        .filter(
            Employment.company_id == company_id,
            Employment.validation_status
            == EmploymentRequestValidationStatus.PENDING,
            ~Employment.is_dismissed,
        )
        .all()
    )
    return [row.id for row in pending]


def _count_inactive_employees(company_id, user_timezone):
    """Approved non-admin employees with last_active_at in the last 30 days
    and no Activity today.

    Uses a correlated NOT EXISTS on Activity (instead of NOT IN subquery)
    which is both safer against NULLs and more amenable to indexed plans.
    """
    today_local = datetime.now(tz=user_timezone).date()
    today_start, _ = _today_window_for_user(user_timezone)
    threshold_30_days = today_start - timedelta(days=30)

    has_activity_today = (
        db.session.query(Activity.id)
        .join(Mission, Activity.mission_id == Mission.id)
        .filter(
            Mission.company_id == company_id,
            ~Activity.is_dismissed,
            Activity.start_time >= today_start,
            Activity.user_id == Employment.user_id,
        )
        .exists()
    )

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
            ~has_activity_today,
            or_(
                Employment.end_date.is_(None),
                Employment.end_date >= today_local,
            ),
        )
        .scalar()
    ) or 0


def _has_any_mission_this_week(company_id, user_timezone):
    """True if the company has at least one non-dismissed activity since Monday."""
    week_start = _week_start_for_user(user_timezone)
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


def _count_auto_validated_missions(company_id, user_timezone):
    """Missions auto-validated by the system today (manager timezone)."""
    today_start, today_end = _today_window_for_user(user_timezone)
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


def get_dashboard_summary(company_id, user_timezone):
    pending_ids = _get_pending_invitations(company_id)
    return DashboardSummary(
        active_missions_count=_count_active_missions(company_id),
        pending_validations_count=_count_pending_validations(company_id),
        pending_invitations_count=len(pending_ids),
        pending_invitation_employment_ids=pending_ids,
        inactive_employees_count=_count_inactive_employees(
            company_id, user_timezone
        ),
        auto_validated_missions_count=(
            _count_auto_validated_missions(company_id, user_timezone)
        ),
        has_any_mission_this_week=_has_any_mission_this_week(
            company_id, user_timezone
        ),
    )
