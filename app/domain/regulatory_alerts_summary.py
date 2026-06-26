from datetime import datetime, time, timedelta, timezone

from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import joinedload

from app import db
from app.data_access.regulation_computation import (
    get_regulation_checks_by_unit,
)
from app.data_access.regulatory_alerts_summary import (
    AlertDayDetail,
    AlertsGroup,
    RegulatoryAlertsSummary,
)
from app.domain.regulations_per_day import (
    EXTRA_NOT_ENOUGH_BREAK,
    EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME,
    NATINF_32083,
)
from app.helpers.submitter_type import SubmitterType
from app.helpers.time import to_tz
from app.models import (
    Activity,
    Company,
    Mission,
    RegulatoryAlert,
    RegulationComputation,
    User,
)
from app.models.regulation_check import UnitType, RegulationCheckType

MAXIMUM_NIGHT_WORK_DAY_TIME_TYPE = "maximumNightWorkDayTime"


def _query_alerts_in_window(start_date, end_date, user_ids):
    """Load alerts in [start_date, end_date) for given users."""
    return (
        RegulatoryAlert.query.options(joinedload(RegulatoryAlert.user))
        .filter(
            RegulatoryAlert.user_id.in_(user_ids),
            RegulatoryAlert.day >= start_date,
            RegulatoryAlert.day < end_date,
            RegulatoryAlert.submitter_type == SubmitterType.ADMIN,
        )
        .all()
    )


def _count_alerts_in_window(start_date, end_date, user_ids):
    """Count alerts in [start_date, end_date), counting "double" alerts
    (NOT_ENOUGH_BREAK + TOO_MUCH_UNINTERRUPTED_WORK_TIME on the same row)
    twice — preserves the historical semantic."""
    base_query = RegulatoryAlert.query.filter(
        RegulatoryAlert.user_id.in_(user_ids),
        RegulatoryAlert.day >= start_date,
        RegulatoryAlert.day < end_date,
        RegulatoryAlert.submitter_type == SubmitterType.ADMIN,
    )
    base_count = base_query.count()
    double_alerts_count = base_query.filter(
        RegulatoryAlert.extra[EXTRA_NOT_ENOUGH_BREAK].as_boolean() == True,
        RegulatoryAlert.extra[
            EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME
        ].as_boolean()
        == True,
    ).count()
    return base_count + double_alerts_count


def query_alerts_for_month(month, user_ids):
    """Legacy entry point: load alerts for `month` and count alerts for
    the previous month. Kept for backward compatibility."""
    start_date = month
    end_date = month + relativedelta(months=1)
    current_month_alerts = _query_alerts_in_window(
        start_date, end_date, user_ids
    )
    previous_start = month + relativedelta(months=-1)
    previous_month_alerts_count = _count_alerts_in_window(
        previous_start, start_date, user_ids
    )
    return current_month_alerts, previous_month_alerts_count


def _has_regulation_computation_in_window(start_date, end_date, user_ids):
    query = db.session.query(RegulationComputation).filter(
        RegulationComputation.user_id.in_(user_ids),
        RegulationComputation.day >= start_date,
        RegulationComputation.day < end_date,
        RegulationComputation.submitter_type == SubmitterType.ADMIN,
    )
    return db.session.query(query.exists()).scalar()


def has_any_regulation_computation(month, user_ids):
    start_date = month
    end_date = month + relativedelta(months=1)
    return _has_regulation_computation_in_window(
        start_date, end_date, user_ids
    )


def _make_unique_day_details(alerts, alert_type, seen_by_type):
    """Build deduplicated AlertDayDetail list for a given alert type."""
    if alert_type not in seen_by_type:
        seen_by_type[alert_type] = {}
    seen = seen_by_type[alert_type]
    result = []
    for a in alerts:
        key = (a.day, a.user_id)
        if key not in seen:
            detail = AlertDayDetail(
                day=a.day,
                user_name=f"{a.user.first_name} {a.user.last_name}",
                user_id=a.user_id,
            )
            seen[key] = detail
            result.append(detail)
    return result


def _append_to_daily_alerts(alerts, alert_type, daily_alerts, seen_by_type):
    """Append alerts to the daily_alerts dict, deduplicating day_details."""
    new_details = _make_unique_day_details(alerts, alert_type, seen_by_type)
    if alert_type in daily_alerts:
        daily_alerts[alert_type].nb_alerts += len(alerts)
        daily_alerts[alert_type].days += [a.day for a in alerts]
        daily_alerts[alert_type].day_details += new_details
    else:
        daily_alerts[alert_type] = AlertsGroup(
            alerts_type=alert_type,
            nb_alerts=len(alerts),
            days=[a.day for a in alerts],
            day_details=new_details,
        )


def _partition_day_night_max_work_alerts(alerts):
    """Split MAXIMUM_WORK_DAY_TIME alerts by sanction code (night = 32083)."""
    day_alerts = []
    night_alerts = []
    for a in alerts:
        if (a.extra or {}).get("sanction_code") == NATINF_32083:
            night_alerts.append(a)
        else:
            day_alerts.append(a)
    return day_alerts, night_alerts


def _append_enough_break_alerts(alerts, daily_alerts, seen_by_type):
    for extra_field in [
        EXTRA_NOT_ENOUGH_BREAK,
        EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME,
    ]:
        extra_alerts = [a for a in alerts if a.extra[extra_field]]
        _append_to_daily_alerts(
            extra_alerts, extra_field, daily_alerts, seen_by_type
        )


def _append_max_work_day_time_alerts(
    alerts, check_type, daily_alerts, seen_by_type
):
    day_alerts, night_alerts = _partition_day_night_max_work_alerts(alerts)
    _append_to_daily_alerts(day_alerts, check_type, daily_alerts, seen_by_type)
    _append_to_daily_alerts(
        night_alerts,
        MAXIMUM_NIGHT_WORK_DAY_TIME_TYPE,
        daily_alerts,
        seen_by_type,
    )


def _append_alerts_for_check(check, alerts, daily_alerts, seen_by_type):
    if check.type == RegulationCheckType.ENOUGH_BREAK:
        _append_enough_break_alerts(alerts, daily_alerts, seen_by_type)
        return
    if check.type == RegulationCheckType.MINIMUM_WORK_DAY_BREAK:
        _append_to_daily_alerts(
            alerts, EXTRA_NOT_ENOUGH_BREAK, daily_alerts, seen_by_type
        )
        return
    if check.type == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME:
        _append_to_daily_alerts(
            alerts,
            EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME,
            daily_alerts,
            seen_by_type,
        )
        return
    if check.type == RegulationCheckType.MAXIMUM_WORK_DAY_TIME:
        _append_max_work_day_time_alerts(
            alerts, check.type, daily_alerts, seen_by_type
        )
        return
    _append_to_daily_alerts(alerts, check.type, daily_alerts, seen_by_type)


def _build_daily_alerts(current_alerts):
    """Group alerts by daily regulation check type."""
    daily_checks = get_regulation_checks_by_unit(unit=UnitType.DAY)
    daily_alerts = {}
    seen_by_type = {}

    for check in daily_checks:
        if check.type == RegulationCheckType.NO_LIC:
            continue
        alerts = [
            a for a in current_alerts if a.regulation_check_id == check.id
        ]
        _append_alerts_for_check(check, alerts, daily_alerts, seen_by_type)

    for group in daily_alerts.values():
        group.days = sorted({*group.days})
        group.day_details = sorted(group.day_details, key=lambda x: x.day)

    return daily_alerts, seen_by_type


def _build_weekly_alerts(current_alerts, reference_date, seen_by_type):
    """Group alerts by weekly regulation check type."""
    weekly_checks = get_regulation_checks_by_unit(
        unit=UnitType.WEEK, date=reference_date
    )
    weekly_alerts = []
    for check in weekly_checks:
        alerts = [
            a for a in current_alerts if a.regulation_check_id == check.id
        ]
        weekly_alerts.append(
            AlertsGroup(
                alerts_type=check.type,
                nb_alerts=len(alerts),
                days=sorted({a.day for a in alerts}),
                day_details=_make_unique_day_details(
                    alerts, check.type, seen_by_type
                ),
            )
        )
    return weekly_alerts


def _count_double_alerts(current_alerts):
    """Count alerts with both uninterrupted work and break violations."""
    return sum(
        1
        for a in current_alerts
        if a.extra
        and a.extra.get(EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME, False)
        and a.extra.get(EXTRA_NOT_ENOUGH_BREAK, False)
    )


def _build_other_company_relations(
    window_start, window_end, user_ids, current_company_id
):
    """Return a dict (user_id, day) -> 'company' | 'establishment' for each
    pair where the user has at least one non-dismissed activity in a company
    other than `current_company_id`, within [window_start, window_end).
    """
    if not user_ids or current_company_id is None:
        return {}

    current_siren = (
        db.session.query(Company.siren)
        .filter(Company.id == current_company_id)
        .scalar()
    )

    # Widen by one day on each side to be safe with user timezones
    sql_start = datetime.combine(
        window_start - timedelta(days=1), time.min, tzinfo=timezone.utc
    )
    sql_end = datetime.combine(
        window_end + timedelta(days=1), time.min, tzinfo=timezone.utc
    )

    rows = (
        db.session.query(
            Activity.user_id, Activity.start_time, User, Company.siren
        )
        .join(Mission, Mission.id == Activity.mission_id)
        .join(Company, Company.id == Mission.company_id)
        .join(User, User.id == Activity.user_id)
        .filter(
            Mission.company_id != current_company_id,
            Activity.user_id.in_(user_ids),
            Activity.start_time >= sql_start,
            Activity.start_time < sql_end,
            ~Activity.is_dismissed,
        )
        .all()
    )

    relations = {}
    for user_id, start_time, user, other_siren in rows:
        # start_time is stored as UTC-naive (cf. DateTimeStoredAsUTC),
        # to_tz adds the UTC tzinfo and converts to the user timezone
        local_day = to_tz(start_time, user.timezone).date()
        if not (window_start <= local_day < window_end):
            continue
        same_siren = (
            current_siren is not None
            and other_siren is not None
            and other_siren == current_siren
        )
        kind = "establishment" if same_siren else "company"
        key = (user_id, local_day)
        if relations.get(key) != "company":
            relations[key] = kind
    return relations


def _mark_other_company_days(alerts_group, relations):
    """Set other_company_relation on every AlertDayDetail whose (user, day)
    matches a key in `relations`."""
    for detail in alerts_group.day_details or []:
        detail.other_company_relation = relations.get(
            (detail.user_id, detail.day)
        )


def get_regulatory_alerts_summary(
    month, user_ids, company_id=None, from_date=None, to_date=None
):
    """Build the regulatory alerts summary.

    By default, loads alerts for the whole `month` plus a count for the
    previous month (used for the month-over-month trend in the regulatory
    panel).

    When `from_date` and `to_date` are both provided, the alert window is
    narrowed to [from_date, to_date) and the previous-month count is
    skipped. This is the recommended mode for the manager homepage, which
    only needs current-week data and was previously over-fetching a full
    month + the cross-company JOIN over ~32 days.
    """
    if from_date is not None and to_date is not None:
        window_start = from_date
        window_end = to_date
        compute_previous = False
    else:
        window_start = month
        window_end = month + relativedelta(months=1)
        compute_previous = True

    if not _has_regulation_computation_in_window(
        window_start, window_end, user_ids
    ):
        return RegulatoryAlertsSummary(
            has_any_computation=False,
            month=month,
            total_nb_alerts=0,
            total_nb_alerts_previous_month=0,
            daily_alerts=[],
            weekly_alerts=[],
        )

    current_alerts = _query_alerts_in_window(
        window_start, window_end, user_ids
    )

    if compute_previous:
        previous_start = month + relativedelta(months=-1)
        previous_count = _count_alerts_in_window(
            previous_start, month, user_ids
        )
    else:
        previous_count = 0

    daily_alerts, seen_by_type = _build_daily_alerts(current_alerts)
    weekly_alerts = _build_weekly_alerts(
        current_alerts, window_start, seen_by_type
    )
    double_alerts_to_add = _count_double_alerts(current_alerts)

    other_relations = _build_other_company_relations(
        window_start=window_start,
        window_end=window_end,
        user_ids=user_ids,
        current_company_id=company_id,
    )
    for group in daily_alerts.values():
        _mark_other_company_days(group, other_relations)
    for group in weekly_alerts:
        _mark_other_company_days(group, other_relations)

    return RegulatoryAlertsSummary(
        month=month,
        has_any_computation=True,
        total_nb_alerts=len(current_alerts) + double_alerts_to_add,
        total_nb_alerts_previous_month=previous_count,
        daily_alerts=daily_alerts.values(),
        weekly_alerts=weekly_alerts,
    )
