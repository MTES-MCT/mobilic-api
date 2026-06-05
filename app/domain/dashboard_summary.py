from datetime import datetime, time, timedelta, timezone

from sqlalchemy import and_, func, or_

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


def _count_active_missions(company_id):
    """Missions with at least one running activity (i.e. an activity whose
    chronometer is still ticking — end_time IS NULL).

    Matches the "En cours" tag shown in the Activities panel: a mission
    where every activity is ended but only awaits worker validation is
    NOT counted here (it belongs to the pending validations counter).
    """
    return (
        db.session.query(func.count(func.distinct(Activity.mission_id)))
        .join(Mission, Activity.mission_id == Mission.id)
        .filter(
            Mission.company_id == company_id,
            ~Activity.is_dismissed,
            Activity.end_time.is_(None),
        )
        .scalar()
    ) or 0


PENDING_VALIDATIONS_WINDOW_DAYS = 31


def _count_pending_validations(company_id):
    """Missions started in the last 31 days that are ended by every user,
    validated by at least one worker, and not yet validated by an admin.
    """
    window_start = datetime.now(tz=timezone.utc).replace(
        tzinfo=None
    ) - timedelta(days=PENDING_VALIDATIONS_WINDOW_DAYS)
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
            Activity.start_time >= window_start,
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

    Mirrors the InactiveEmployeesDropdown frontend logic: today's exclusion
    is based on real activity (Activity rows) rather than on last_active_at,
    so a user whose last_active_at falls today but who has not started any
    activity yet is still surfaced as inactive (the dropdown does the same).
    """
    today_local = datetime.now(tz=user_timezone).date()
    today_start, _ = _today_window_for_user(user_timezone)
    threshold_30_days = today_start - timedelta(days=30)

    active_user_ids_today = (
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
            Employment.user_id.notin_(db.session.query(active_user_ids_today)),
            or_(
                Employment.end_date.is_(None),
                Employment.end_date >= today_local,
            ),
        )
        .scalar()
    ) or 0


def _has_any_mission_this_week(company_id, user_timezone):
    """True if the company has at least one non-dismissed activity since Monday."""
    today_local = datetime.now(tz=user_timezone).date()
    monday = today_local - timedelta(days=today_local.weekday())
    week_start = from_tz(datetime.combine(monday, time.min), user_timezone)
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
    """Missions auto-validated by the system today.

    Limited to today's validations so the counter reflects the
    end-of-day batch the manager can still react to. The day boundary
    follows the manager's own timezone so a validation made at 23h
    local time is still counted in the manager's "today".
    """
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
