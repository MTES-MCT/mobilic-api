import json
from collections import namedtuple
from datetime import datetime, timedelta

from app import db
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.errors import InvalidResourceError
from app.helpers.time import (
    get_dates_range,
    get_first_day_of_week,
    get_last_day_of_week,
    to_datetime,
)
from app.models import RegulationCheck
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.models.regulatory_alert import RegulatoryAlert
from sqlalchemy import desc

DAY = 86400
HOUR = 3600
MINUTE = 60

ComputationResult = namedtuple(
    "ComputationResult", ["success", "extra"], defaults=(False, None)
)


def compute_regulations(user, period_start, period_end, submitter_type):

    # Compute daily rules for each day
    for day in get_dates_range(period_start, period_end):
        compute_regulations_per_day(user, day, submitter_type)

    # Compute weekly rules
    from_date = get_first_day_of_week(period_start)
    until_date = get_last_day_of_week(period_end)

    work_days, _ = group_user_events_by_day_with_limit(
        user, from_date=from_date, until_date=until_date
    )
    weeks = group_user_events_by_week(work_days, from_date, until_date)

    for week in weeks:
        compute_regulations_per_week(user, week, submitter_type)


def compute_regulations_per_day(user, day, submitter_type):
    previous_day = day - timedelta(1)
    next_day = day + timedelta(2)
    # FIXME handle submitter correctly
    (
        work_days_over_current_past_and_next_days,
        _,
    ) = group_user_events_by_day_with_limit(
        user,
        from_date=previous_day,
        until_date=next_day,
    )

    day_start_time = to_datetime(day)
    day_end_time = day_start_time + timedelta(1)
    activity_groups_to_take_into_account = list(
        filter(
            lambda x: x.start_time <= day_end_time
            and x.end_time > day_start_time,
            work_days_over_current_past_and_next_days,
        )
    )

    regulatory_checks = {
        RegulationCheckType.MINIMUM_DAILY_REST: check_min_daily_rest,
        RegulationCheckType.MAXIMUM_WORK_DAY_TIME: check_max_work_day_time,
        RegulationCheckType.MINIMUM_WORK_DAY_BREAK: check_min_work_day_break,
        RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME: check_max_uninterrupted_work_time,
    }

    for type, computation in regulatory_checks.items():
        # IMPROVE: instead of using the latest, use the one valid for the day target
        regulation_check = (
            RegulationCheck.query.filter(RegulationCheck.type == type)
            .order_by(desc(RegulationCheck.date_application_start))
            .first()
        )
        if not regulation_check:
            raise InvalidResourceError(
                f"Missing regulation check of type {type}"
            )

        success, extra = computation(
            activity_groups_to_take_into_account, regulation_check
        )

        if not success:
            extra_json = None
            if extra is not None:
                extra_json = json.dumps(extra)
            regulatory_alert = RegulatoryAlert(
                day=day,
                extra=extra_json,
                submitter_type=submitter_type,
                user=user,
                regulation_check=regulation_check,
            )
            db.session.add(regulatory_alert)


def compute_regulations_per_week(user, week, submitter_type):
    regulatory_checks = {
        RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK: check_max_worked_day_in_week,
    }

    for type, computation in regulatory_checks.items():
        # IMPROVE: instead of using the latest, use the one valid for the day target
        regulation_check = (
            RegulationCheck.query.filter(RegulationCheck.type == type)
            .order_by(desc(RegulationCheck.date_application_start))
            .first()
        )
        if not regulation_check:
            raise InvalidResourceError(
                f"Missing regulation check of type {type}"
            )

        success, extra = computation(week, regulation_check)

        if not success:
            extra_json = None
            if extra is not None:
                extra_json = json.dumps(extra)
            regulatory_alert = RegulatoryAlert(
                day=week["start"],
                extra=extra_json,
                submitter_type=submitter_type,
                user=user,
                regulation_check=regulation_check,
            )
            db.session.add(regulatory_alert)


def check_min_daily_rest(activity_groups, regulation_check):
    LONG_BREAK_DURATION_IN_HOURS = regulation_check.variables[
        "LONG_BREAK_DURATION_IN_HOURS"
    ]

    total_work_duration = 0
    for group in activity_groups:
        total_work_duration += (
            group.end_time - group.start_time
        ).total_seconds()

    success = total_work_duration <= (24 - LONG_BREAK_DURATION_IN_HOURS) * HOUR
    return ComputationResult(success=success)


def check_max_work_day_time(activity_groups, regulation_check):
    MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS = regulation_check.variables[
        "MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS"
    ]
    MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS = regulation_check.variables[
        "MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS"
    ]
    extra = None
    for group in activity_groups:
        night_work = group.total_night_work_duration > 0
        max_time_in_hours = (
            MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS
            if night_work
            else MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS
        )
        extra = dict(
            night_work=night_work, max_time_in_hours=max_time_in_hours
        )
        if group.total_work_duration > max_time_in_hours * HOUR:
            return ComputationResult(success=False, extra=extra)

    return ComputationResult(success=True, extra=extra)


def check_min_work_day_break(activity_groups, regulation_check):
    MINIMUM_DURATION_INDIVIDUAL_BREAK_IN_MIN = regulation_check.variables[
        "MINIMUM_DURATION_INDIVIDUAL_BREAK_IN_MIN"
    ]
    MINIMUM_DURATION_WORK_IN_HOURS_1 = regulation_check.variables[
        "MINIMUM_DURATION_WORK_IN_HOURS_1"
    ]
    MINIMUM_DURATION_WORK_IN_HOURS_2 = regulation_check.variables[
        "MINIMUM_DURATION_WORK_IN_HOURS_2"
    ]
    MINIMUM_DURATION_BREAK_IN_MIN_1 = regulation_check.variables[
        "MINIMUM_DURATION_BREAK_IN_MIN_1"
    ]
    MINIMUM_DURATION_BREAK_IN_MIN_2 = regulation_check.variables[
        "MINIMUM_DURATION_BREAK_IN_MIN_2"
    ]
    # IMPROVE: we may store a map key-value for these period values

    total_work_duration_s = 0
    total_break_time_s = 0
    latest_work_time = None
    for group in activity_groups:
        total_work_duration_s += group.total_work_duration
        for activity in group.activities:
            if (
                latest_work_time is not None
                and activity.start_time - latest_work_time
                >= timedelta(minutes=MINIMUM_DURATION_INDIVIDUAL_BREAK_IN_MIN)
            ):
                total_break_time_s += (
                    activity.start_time - latest_work_time
                ).total_seconds()
            latest_work_time = activity.end_time

    if total_work_duration_s > MINIMUM_DURATION_WORK_IN_HOURS_1 * HOUR:
        if (
            total_work_duration_s <= MINIMUM_DURATION_WORK_IN_HOURS_2 * HOUR
            and total_break_time_s < MINIMUM_DURATION_BREAK_IN_MIN_1 * MINUTE
        ):
            return ComputationResult(
                success=False,
                extra=dict(
                    min_time_in_minutes=MINIMUM_DURATION_BREAK_IN_MIN_1
                ),
            )
        elif (
            total_work_duration_s > MINIMUM_DURATION_WORK_IN_HOURS_2 * HOUR
            and total_break_time_s < MINIMUM_DURATION_BREAK_IN_MIN_2 * MINUTE
        ):
            return ComputationResult(
                success=False,
                extra=dict(
                    min_time_in_minutes=MINIMUM_DURATION_BREAK_IN_MIN_2
                ),
            )

    return ComputationResult(success=True)


def check_max_uninterrupted_work_time(activity_groups, regulation_check):
    MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS = (
        regulation_check.variables[
            "MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS"
        ]
    )

    # exit loop if we find a consecutive series of activites with span time > MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK
    now = datetime.now()
    current_uninterrupted_work_duration = 0
    latest_work_time = None

    for group in activity_groups:
        for activity in group.activities:
            if activity.type is ActivityType.TRANSFER:
                continue
            if (
                latest_work_time is None
                or activity.start_time > latest_work_time
            ):
                current_uninterrupted_work_duration = 0
            end_time = (
                activity.end_time if activity.end_time is not None else now
            )
            current_uninterrupted_work_duration += (
                end_time - activity.start_time
            ).total_seconds()
            if (
                current_uninterrupted_work_duration
                > MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS * HOUR
            ):
                return ComputationResult(success=False)
            latest_work_time = activity.end_time

    return ComputationResult(success=True)


# Inspired from app/helpers/pdf/work_days.py _generate_work_days_pdf
def group_user_events_by_week(
    work_days,
    start_date,
    end_date,
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
                "overlap_previous_day": wd.is_first_mission_overlapping_with_previous_day,
                "overlap_next_day": wd.is_last_mission_overlapping_with_next_day,
            }
        )

    # compute rest duration for each week
    for week in weeks:
        week["rest_duration_s"] = compute_weekly_rest_duration(week)

    return weeks


def compute_weekly_rest_duration(week):
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
                current_day_time = to_datetime(current_day)
                current_outer_break += (
                    day["start_time"] - current_day_time
                ).total_seconds()
                if current_outer_break > max_outer_break:
                    max_outer_break = current_outer_break
                    current_outer_break = 0

            if day["overlap_next_day"] is False:
                end_of_day = datetime(
                    day["start_time"].year,
                    day["start_time"].month,
                    day["start_time"].day + 1,
                )
                current_outer_break = (
                    end_of_day - day["end_time"]
                ).total_seconds()

        current_day += timedelta(days=1)

    if current_outer_break > max_outer_break:
        max_outer_break = current_outer_break

    return max_outer_break


def check_max_worked_day_in_week(week, regulation_check):
    MAXIMUM_DAY_WORKED_BY_WEEK = regulation_check.variables[
        "MAXIMUM_DAY_WORKED_BY_WEEK"
    ]
    if week["worked_days"] > MAXIMUM_DAY_WORKED_BY_WEEK:
        return ComputationResult(success=False, extra=dict(too_many_days=True))

    MINIMUM_WEEKLY_BREAK_IN_HOURS = regulation_check.variables[
        "MINIMUM_WEEKLY_BREAK_IN_HOURS"
    ]
    if week["rest_duration_s"] < MINIMUM_WEEKLY_BREAK_IN_HOURS * HOUR:
        return ComputationResult(
            success=False, extra=dict(rest_duration_s=week["rest_duration_s"])
        )

    return ComputationResult(success=True)
