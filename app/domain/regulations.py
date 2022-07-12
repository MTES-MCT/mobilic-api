from datetime import datetime, timedelta

from sqlalchemy import desc
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.errors import InvalidResourceError
from app.helpers.time import FR_TIMEZONE, to_datetime
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheckType
from app.models.regulation_day import RegulationDay
from app.models import RegulationCheck
from app import db
import json

DAY = 86400
HOUR = 3600
MINUTE = 60
tz = FR_TIMEZONE  # TODO dynamic tz?


def compute_regulations(user, period_start, period_end, submitter_type):
    # foreach day between period_start & period_end
    #  compute_regulation_per_day(user, day, submitter_type)
    # foreach week between period_start & period_end
    #  compute_regulations_per_week(user, week, submitter_type)
    return


def compute_regulations_per_day(user, day_start, submitter_type):
    previous_day = day_start - timedelta(1)
    next_day = day_start + timedelta(2)

    # FIXME handle submitter correctly
    (
        work_days_over_current_past_and_next_days,
        _,
    ) = group_user_events_by_day_with_limit(
        user,
        from_date=previous_day,
        until_date=next_day,
    )

    day_start_time = to_datetime(day_start, tz_for_date=tz)
    day_end_time = day_start_time + timedelta(1)
    activity_groups_to_take_into_account = list(
        filter(
            lambda x: x.start_time <= day_end_time
            and x.end_time > day_start_time,
            work_days_over_current_past_and_next_days,
        )
    )

    check_min_daily_rest(
        activity_groups_to_take_into_account, user, day_start, submitter_type
    )

    check_max_work_day_time(
        activity_groups_to_take_into_account, user, day_start, submitter_type
    )

    check_min_work_day_break(
        activity_groups_to_take_into_account, user, day_start, submitter_type
    )

    check_max_uninterrupted_work_time(
        activity_groups_to_take_into_account, user, day_start, submitter_type
    )

    return


def compute_regulations_per_week(user, week, submitter_type):
    # get activities from missions of user validated by submitter_type with week included in activity date
    # check each week regulation
    return


def check_min_daily_rest(
    activity_groups,
    # inner_long_breaks,
    user,
    day_start,
    submitter_type,
):
    regulation_check = (
        RegulationCheck.query.filter(
            RegulationCheck.type == RegulationCheckType.MINIMUM_DAILY_REST
        )
        .order_by(desc(RegulationCheck.date_application_start))
        .first()
    )

    if not regulation_check:
        raise InvalidResourceError(
            "Missing regulation check of type MINIMUM_DAILY_REST"
        )

    LONG_BREAK_DURATION_IN_HOURS = regulation_check.variables[
        "LONG_BREAK_DURATION_IN_HOURS"
    ]
    success = all(
        group.end_time - group.start_time
        <= timedelta(hours=24 - LONG_BREAK_DURATION_IN_HOURS)
        for group in activity_groups
    )

    # rest_duration = None
    # if len(inner_long_breaks) > 0:
    #     rest_duration = inner_long_breaks[0].duration

    regulation_day = RegulationDay(
        day=day_start,
        success=success,
        # extra=json.dumps(dict(rest_duration)),
        submitter_type=submitter_type,
        user=user,
        regulation_check=regulation_check,
    )
    db.session.add(regulation_day)
    return


def check_max_work_day_time(activity_groups, user, day_start, submitter_type):
    regulation_check = (
        RegulationCheck.query.filter(
            RegulationCheck.type == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
        )
        .order_by(desc(RegulationCheck.date_application_start))
        .first()
    )

    if not regulation_check:
        raise InvalidResourceError(
            "Missing regulation check of type MAXIMUM_WORK_DAY_TIME"
        )

    MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS = regulation_check.variables[
        "MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS"
    ]
    MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS = regulation_check.variables[
        "MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS"
    ]
    success = True
    for group in activity_groups:
        night_work = group.total_night_work_duration > 0
        max_time_in_hours = (
            MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS
            if night_work
            else MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS
        )
        if group.total_work_duration > max_time_in_hours * HOUR:
            success = False
            break

    regulation_day = RegulationDay(
        day=day_start,
        success=success,
        extra=json.dumps(
            dict(night_work=night_work, max_time_in_hours=max_time_in_hours)
        ),
        submitter_type=submitter_type,
        user=user,
        regulation_check=regulation_check,
    )
    db.session.add(regulation_day)
    return


def check_min_work_day_break(activity_groups, user, day_start, submitter_type):
    regulation_check = (
        RegulationCheck.query.filter(
            RegulationCheck.type == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
        )
        .order_by(desc(RegulationCheck.date_application_start))
        .first()
    )

    if not regulation_check:
        raise InvalidResourceError(
            "Missing regulation check of type MINIMUM_WORK_DAY_BREAK"
        )

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

    total_work_duration = 0
    total_break_time_s = 0
    latest_work_time = None
    for group in activity_groups:
        total_work_duration += group.total_work_duration
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

    success = True
    if total_work_duration > MINIMUM_DURATION_WORK_IN_HOURS_1 * HOUR:
        if (
            total_work_duration <= MINIMUM_DURATION_WORK_IN_HOURS_1 * HOUR
            and total_break_time_s < MINIMUM_DURATION_BREAK_IN_MIN_1 * MINUTE
        ):
            success = False
        elif (
            total_work_duration > MINIMUM_DURATION_WORK_IN_HOURS_2 * HOUR
            and total_break_time_s < MINIMUM_DURATION_BREAK_IN_MIN_2 * MINUTE
        ):
            success = False

    regulation_day = RegulationDay(
        day=day_start,
        success=success,
        submitter_type=submitter_type,
        user=user,
        regulation_check=regulation_check,
    )
    db.session.add(regulation_day)
    return


def check_max_uninterrupted_work_time(
    activity_groups, user, day_start, submitter_type
):
    regulation_check = (
        RegulationCheck.query.filter(
            RegulationCheck.type
            == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME
        )
        .order_by(desc(RegulationCheck.date_application_start))
        .first()
    )

    if not regulation_check:
        raise InvalidResourceError(
            "Missing regulation check of type MAXIMUM_UNINTERRUPTED_WORK_TIME"
        )

    MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS = (
        regulation_check.variables[
            "MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS"
        ]
    )

    # exit loop if we find a consecutive series of activites with span time > MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK
    now = datetime.now()
    current_uninterrupted_work_duration = 0
    latest_work_time = None
    success = True

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
                success = False
                break
            latest_work_time = activity.end_time
        if success is False:
            break

    regulation_day = RegulationDay(
        day=day_start,
        success=success,
        submitter_type=submitter_type,
        user=user,
        regulation_check=regulation_check,
    )
    db.session.add(regulation_day)
    return


# TODO remove if not used
# def daily_total_effective_work(activities):
#     now = datetime.now()
#     filtered_activities = list(
#         filter(lambda a: a.type != ActivityType.TRANSFER, activities))
#     effective_works = list(
#         map(lambda a: (a.end_time or now) - a.start_time, filtered_activities))
#     return reduce(lambda x, y: x + y, effective_works, 0)


# TODO remove if not used
# def is_night_work(activity, START_DAY_WORK_HOUR):
#     if activity.type == ActivityType.TRANSFER:
#         return False
#     if activity.end_time == activity.start_time:
#         return False
#     start_time = to_datetime(
#         activity.start_time, tz_for_date=tz)
#     if start_time.hour < START_DAY_WORK_HOUR:
#         return True
#     next_midnight = to_datetime(
#         activity.start_time + DAY, tz_for_date=tz)
#     next_midnight.hour = 0
#     next_midnight.minute = 0
#     next_midnight.second = 0
#     end_time = activity.end_time if activity.end_time else datetime.now()
#     return end_time > next_midnight
