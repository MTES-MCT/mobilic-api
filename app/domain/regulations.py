from datetime import date, datetime, timedelta, timezone

from app import app, db
from app.domain.regulations_per_day import compute_regulations_per_day
from app.domain.regulations_per_week import compute_regulations_per_week
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.regulations_utils import DAY
from app.helpers.submitter_type import SubmitterType
from app.helpers.time import (
    get_dates_range,
    get_first_day_of_week,
    get_last_day_of_week,
    to_datetime,
    get_uninterrupted_datetime_ranges,
)
from app.models import RegulationCheck
from app.models.regulation_check import UnitType
from app.models.regulation_computation import RegulationComputation
from app.models.regulatory_alert import RegulatoryAlert
from dateutil.tz import gettz


def compute_regulations(user, period_start, period_end, submitter_type):
    period_start = period_start - timedelta(days=1)
    week_period_start = get_first_day_of_week(period_start)
    week_period_end = get_last_day_of_week(period_end)

    clean_current_alerts(
        user,
        period_start,
        period_end,
        week_period_start,
        week_period_end,
        submitter_type,
    )

    user_timezone = gettz(user.timezone_name)

    # Next day is needed for some computation rules
    day_after_period_end = period_end + timedelta(days=1)
    (
        work_days_over_current_past_and_next_days,
        _,
    ) = group_user_events_by_day_with_limit(
        user,
        from_date=week_period_start,
        until_date=min(week_period_end, day_after_period_end),
        tz=user_timezone,
        only_missions_validated_by_admin=submitter_type == SubmitterType.ADMIN,
        only_missions_validated_by_user=submitter_type
        == SubmitterType.EMPLOYEE,
    )

    # Compute daily rules for each day
    for day in get_dates_range(period_start, period_end):
        compute_regulations_per_day(
            user,
            day,
            submitter_type,
            work_days_over_current_past_and_next_days,
            tz=user_timezone,
        )
        mark_day_as_computed(user, day, submitter_type)

    # Compute weekly rules
    weeks = group_user_events_by_week(
        work_days_over_current_past_and_next_days,
        week_period_start,
        week_period_end,
        tz=user_timezone,
    )
    for week in weeks:
        compute_regulations_per_week(user, week, submitter_type)


def clean_current_alerts(
    user,
    day_compute_start,
    day_compute_end,
    week_compute_start,
    week_compute_end,
    submitter_type,
):
    db.session.query(RegulatoryAlert).filter(
        RegulatoryAlert.user == user,
        RegulatoryAlert.submitter_type == submitter_type,
        RegulatoryAlert.day >= day_compute_start,
        RegulatoryAlert.day <= day_compute_end,
        RegulatoryAlert.regulation_check.has(
            RegulationCheck.unit == UnitType.DAY
        ),
    ).delete(
        synchronize_session=False
    )  # https://docs.sqlalchemy.org/en/14/orm/session_basics.html#selecting-a-synchronization-strategy

    db.session.query(RegulatoryAlert).filter(
        RegulatoryAlert.user == user,
        RegulatoryAlert.submitter_type == submitter_type,
        RegulatoryAlert.day >= week_compute_start,
        RegulatoryAlert.day <= week_compute_end,
        RegulatoryAlert.regulation_check.has(
            RegulationCheck.unit == UnitType.WEEK
        ),
    ).delete(synchronize_session=False)


# Inspired from app/helpers/pdf/work_days.py _generate_work_days_pdf
def group_user_events_by_week(
    work_days,
    start_date,
    end_date,
    tz,
):
    # build weeks
    weeks = []
    current_week = get_first_day_of_week(start_date)
    last_week = get_first_day_of_week(end_date)
    while current_week <= last_week:
        weeks.append(
            {
                "start": current_week,
                "end": current_week + timedelta(days=6),
                "worked_days": 0,
                "days": [],
            }
        )
        current_week += timedelta(days=7)

    # add work days by week
    for wd in work_days:
        week = next(
            filter(
                lambda w, wd=wd: w["start"] == get_first_day_of_week(wd.day),
                weeks,
            ),
            None,
        )
        week["worked_days"] += 1
        week["days"].append(
            {
                "date": wd.day,
                "start_time": wd.start_time,
                "end_time": wd.end_time or wd.end_of_day,
                "end_day": wd.end_of_day,
                "overlap_previous_day": wd.is_first_mission_overlapping_with_previous_day,
                "overlap_next_day": wd.is_last_mission_overlapping_with_next_day,
            }
        )

    # compute rest duration for each week
    for week in weeks:
        week["rest_duration_s"] = compute_weekly_rest_duration(week, tz)

    return weeks


def compute_weekly_rest_duration(week, tz):
    current_outer_break = 0
    max_outer_break = 0
    current_day = week["start"]
    while current_day <= week["end"]:
        day = next(
            filter(lambda d, cd=current_day: d["date"] == cd, week["days"]),
            None,
        )

        if day is None:
            current_outer_break += DAY

        else:

            if day["overlap_previous_day"] is False:
                current_day_time = to_datetime(current_day, tz_for_date=tz)
                current_outer_break += (
                    day["start_time"] - current_day_time
                ).total_seconds()

                if current_outer_break > max_outer_break:
                    max_outer_break = current_outer_break

                current_outer_break = 0

            if day["overlap_next_day"] is False:
                current_outer_break = (
                    day["end_day"] - day["end_time"]
                ).total_seconds()

        current_day += timedelta(days=1)

    if current_outer_break > max_outer_break:
        max_outer_break = current_outer_break

    return max_outer_break


def compute_regulation_for_user(user):
    # on pourrait ajouter un PERIOD_START et un period_END

    #####
    # CLEAN previous data
    # This is mainly done to remove wrongly computed data
    # This could be optional ?
    ####

    # Determine period start and end to clear previous alerts
    first_user_activity = user.first_activity_after(None)
    today = date.today()
    last_user_activity = user.latest_activity_before(to_datetime(today))
    period_start = first_user_activity.start_time.date()
    period_end = (
        last_user_activity.end_time.date()
        if last_user_activity.end_time
        else today
    )
    period_start = period_start - timedelta(days=1)
    week_period_start = get_first_day_of_week(period_start)
    week_period_end = get_last_day_of_week(period_end)

    # Maybe we flagged some day as Computed by mistake before ?
    db.session.query(RegulationComputation).filter(
        RegulationComputation.user == user,
        RegulationComputation.day >= period_start,
        RegulationComputation.day <= period_end,
    ).delete(synchronize_session=False)

    # If we don't recompute on same time periods later, some alerts wouldn't be removed
    for submitter_type in [SubmitterType.ADMIN, SubmitterType.EMPLOYEE]:
        clean_current_alerts(
            user,
            period_start,
            period_end,
            week_period_start,
            week_period_end,
            submitter_type,
        )
    ######

    #####
    # Compute alerts
    #####
    for submitter_type in [SubmitterType.ADMIN, SubmitterType.EMPLOYEE]:
        (work_days, _) = group_user_events_by_day_with_limit(
            user=user,
            include_dismissed_or_empty_days=False,
            only_missions_validated_by_admin=submitter_type
            == SubmitterType.ADMIN,
            only_missions_validated_by_user=submitter_type
            == SubmitterType.EMPLOYEE,
        )
        time_ranges = get_uninterrupted_datetime_ranges(
            [wd.day for wd in work_days]
        )
        for time_range in time_ranges:
            compute_regulations(
                user, time_range[0], time_range[1], submitter_type
            )
    ######


def mark_day_as_computed(user, day, submitter_type):
    already_computed = RegulationComputation.query.filter(
        RegulationComputation.user_id == user.id,
        RegulationComputation.day == day,
        RegulationComputation.submitter_type == submitter_type,
    ).one_or_none()

    if not already_computed:
        regulation_computation = RegulationComputation(
            day=day,
            user=user,
            submitter_type=submitter_type,
        )
        db.session.add(regulation_computation)
