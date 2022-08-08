import json
from datetime import datetime, timedelta

from app import db
from app.helpers.errors import InvalidResourceError
from app.helpers.regulations_utils import HOUR, MINUTE, ComputationResult
from app.helpers.time import seconds_between, to_datetime
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheck, RegulationCheckType
from app.models.regulatory_alert import RegulatoryAlert
from sqlalchemy import desc


def compute_regulations_per_day(
    user, day, submitter_type, work_days_over_current_past_and_next_days
):
    day_start_time = to_datetime(day)
    day_end_time = day_start_time + timedelta(1)
    activity_groups_to_take_into_account = list(
        filter(
            lambda x: x.start_time <= day_end_time
            and x.end_time > day_start_time,
            work_days_over_current_past_and_next_days,
        )
    )

    for type, computation in DAILY_REGULATION_CHECKS.items():
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


def check_min_daily_rest(activity_groups, regulation_check):
    LONG_BREAK_DURATION_IN_HOURS = regulation_check.variables[
        "LONG_BREAK_DURATION_IN_HOURS"
    ]

    total_work_duration = 0
    for group in activity_groups:
        total_work_duration += seconds_between(
            group.end_time, group.start_time
        )

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
        night_work = group.total_night_work_legislation_duration > 0
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
                total_break_time_s += seconds_between(
                    activity.start_time, latest_work_time
                )
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
            current_uninterrupted_work_duration += seconds_between(
                end_time, activity.start_time
            )
            if (
                current_uninterrupted_work_duration
                > MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS * HOUR
            ):
                return ComputationResult(success=False)
            latest_work_time = activity.end_time

    return ComputationResult(success=True)


DAILY_REGULATION_CHECKS = {
    RegulationCheckType.MINIMUM_DAILY_REST: check_min_daily_rest,
    RegulationCheckType.MAXIMUM_WORK_DAY_TIME: check_max_work_day_time,
    RegulationCheckType.MINIMUM_WORK_DAY_BREAK: check_min_work_day_break,
    RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME: check_max_uninterrupted_work_time,
}
