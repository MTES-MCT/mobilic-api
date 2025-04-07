from datetime import datetime, timedelta

from sqlalchemy import desc

from app import db
from app.domain.regulations_helper import resolve_variables
from app.helpers.errors import InvalidResourceError
from app.helpers.regulations_utils import (
    HOUR,
    MINUTE,
    ComputationResult,
    Break,
)
from app.helpers.time import to_datetime
from app.models.activity import ActivityType
from app.models.regulation_check import RegulationCheck, RegulationCheckType
from app.models.regulatory_alert import RegulatoryAlert

NATINF_11292 = "NATINF 11292"
NATINF_32083 = "NATINF 32083"
NATINF_20525 = "NATINF 20525"
NATINF_35187 = "NATINF 35187"
SANCTION_CODE = "Non-respect du Code des transports"


def filter_work_days_to_current_day(work_days, day_start_time, day_end_time):
    return list(
        filter(
            lambda x: x.start_time <= day_end_time
            and x.end_time
            and x.end_time > day_start_time,
            work_days,
        )
    )


def filter_work_days_to_current_and_next_day(
    work_days, day_start_time, day_end_time
):
    return list(
        filter(
            lambda x: x.start_time <= day_end_time + timedelta(days=1)
            and x.end_time
            and x.end_time > day_start_time,
            work_days,
        )
    )


def compute_regulations_per_day(
    user,
    business,
    day,
    submitter_type,
    work_days_over_current_past_and_next_days,
    tz,
):
    day_start_time = to_datetime(day, tz_for_date=tz)
    day_end_time = day_start_time + timedelta(days=1)
    for type, regulation_functions in DAILY_REGULATION_CHECKS.items():
        work_days_filter = regulation_functions[1]
        computation = regulation_functions[0]
        # IMPROVE: instead of using the latest, use the one valid for the day target
        regulation_check = (
            RegulationCheck.query.filter(RegulationCheck.type == type)
            .order_by(desc(RegulationCheck.date_application_start))
            .first()
        )

        # To be used locally on init regulation alerts only!
        # regulation_check = next(
        #     (x for x in get_regulation_checks() if x.type == type), None
        # )

        if not regulation_check:
            raise InvalidResourceError(
                f"Missing regulation check of type {type}"
            )

        activity_groups_to_take_into_account = work_days_filter(
            work_days_over_current_past_and_next_days,
            day_start_time,
            day_end_time,
        )

        success, extra = computation(
            activity_groups_to_take_into_account,
            regulation_check,
            day_start_time,
            business,
        )

        if not success:
            regulatory_alert = RegulatoryAlert(
                day=day,
                extra=extra,
                submitter_type=submitter_type,
                user=user,
                regulation_check_id=regulation_check.id,
                business=business,
            )
            db.session.add(regulatory_alert)


def check_min_daily_rest(
    activity_groups, regulation_check, day_to_check_start_time, business
):
    dict_variables = resolve_variables(regulation_check.variables, business)
    LONG_BREAK_DURATION_IN_HOURS = dict_variables[
        "LONG_BREAK_DURATION_IN_HOURS"
    ]
    extra = dict(min_daily_break_in_hours=LONG_BREAK_DURATION_IN_HOURS)

    all_activities = []
    for group in activity_groups:
        all_activities = all_activities + group.activities

    if len(all_activities) == 0:
        success = True
    else:
        long_breaks = get_long_breaks(all_activities, regulation_check)

        # We consider the end of the last period as the beginning of a long break.
        long_breaks.append(
            Break(
                start_time=activity_groups[-1].end_time,
                end_time=activity_groups[-1].end_time
                + timedelta(hours=LONG_BREAK_DURATION_IN_HOURS),
            )
        )

        # We remove activities that are not included in the day to check.
        day_to_check_end_time = day_to_check_start_time + timedelta(days=1)
        all_activities_for_the_day = list(
            filter(
                lambda activity: activity.start_time < day_to_check_end_time
                and activity.end_time
                and activity.end_time >= day_to_check_start_time,
                all_activities,
            )
        )

        previous_long_break = None
        success = True

        # We remove all the activities covered by long breaks
        for long_break in long_breaks:

            # Identify activities which should be covered by long break
            activities_for_the_day_related_to_long_break = [
                a
                for a in all_activities_for_the_day
                if a.start_time < long_break.end_time
            ]
            activities_related_to_long_break = [
                a for a in all_activities if a.start_time < long_break.end_time
            ]
            if previous_long_break:
                activities_for_the_day_related_to_long_break = [
                    a
                    for a in activities_for_the_day_related_to_long_break
                    if a.start_time >= previous_long_break.end_time
                ]
                activities_related_to_long_break = [
                    a
                    for a in activities_related_to_long_break
                    if a.start_time >= previous_long_break.end_time
                ]

            cover_period_start = (
                long_break.start_time
                + timedelta(hours=LONG_BREAK_DURATION_IN_HOURS)
                - timedelta(days=1)
            )
            activities_not_covered_by_long_break = [
                activity
                for activity in activities_for_the_day_related_to_long_break
                if activity.start_time < cover_period_start
            ]

            if len(activities_not_covered_by_long_break) > 0:
                success = False
                extra[
                    "breach_period_start"
                ] = activities_not_covered_by_long_break[
                    0
                ].start_time.isoformat()
                breach_period_end = activities_not_covered_by_long_break[
                    0
                ].start_time + timedelta(days=1)
                extra["breach_period_end"] = breach_period_end.isoformat()
                longest_inner_break = get_longest_inner_break(
                    activities_related_to_long_break,
                )
                extra["breach_period_max_break_in_seconds"] = (
                    longest_inner_break.seconds
                    if longest_inner_break.days == 0
                    else 0
                )
                extra["sanction_code"] = NATINF_20525
                break

            previous_long_break = long_break

    return ComputationResult(success=success, extra=extra)


def get_longest_inner_break(activities):
    period_end = activities[0].start_time + timedelta(days=1)
    if len(activities) == 1:
        return period_end - activities[-1].end_time

    activities = list(set(activities))
    activities.sort(key=lambda activity: activity.start_time)

    candidates = [
        activities[idx_activity].start_time
        - activities[idx_activity - 1].end_time
        for idx_activity in range(1, len(activities))
    ]
    candidates.append(period_end - activities[-1].end_time)
    candidates.sort()
    return candidates[-1]


def get_long_breaks(activities, regulation_check):
    LONG_BREAK_DURATION_IN_HOURS = regulation_check.variables[
        "LONG_BREAK_DURATION_IN_HOURS"
    ]
    previous_activity = None
    long_breaks = []
    for activity in activities:
        if previous_activity:
            if (
                activity.start_time - previous_activity.end_time
            ).total_seconds() >= LONG_BREAK_DURATION_IN_HOURS * HOUR:
                long_breaks.append(
                    Break(
                        start_time=previous_activity.end_time,
                        end_time=activity.start_time,
                    )
                )
        previous_activity = activity
    return long_breaks


def check_max_work_day_time(activity_groups, regulation_check, business):

    dict_variables = resolve_variables(regulation_check.variables, business)
    MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS = dict_variables[
        "MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS"
    ]
    MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS = dict_variables[
        "MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS"
    ]
    AMPLITUDE_TRIGGER_IN_HOURS = dict_variables.get(
        "AMPLITUDE_TRIGGER_IN_HOURS", None
    )
    MAXIMUM_DURATION_OF_DAY_WORK_IF_HIGH_AMPLITUDE_IN_HOURS = (
        dict_variables.get(
            "MAXIMUM_DURATION_OF_DAY_WORK_IF_HIGH_AMPLITUDE_IN_HOURS", None
        )
    )
    extra = None
    for group in activity_groups:
        max_work_day_time_in_hours = MAXIMUM_DURATION_OF_DAY_WORK_IN_HOURS

        # For some TRV businesses, max work day time is different if amplitude is above a particular value
        if (
            AMPLITUDE_TRIGGER_IN_HOURS
            and MAXIMUM_DURATION_OF_DAY_WORK_IF_HIGH_AMPLITUDE_IN_HOURS
        ):
            amplitude = group.service_duration
            if amplitude > AMPLITUDE_TRIGGER_IN_HOURS * HOUR:
                max_work_day_time_in_hours = (
                    MAXIMUM_DURATION_OF_DAY_WORK_IF_HIGH_AMPLITUDE_IN_HOURS
                )

        night_work = group.total_night_work_legislation_duration > 0
        max_time_in_hours = (
            MAXIMUM_DURATION_OF_NIGHT_WORK_IN_HOURS
            if night_work
            else max_work_day_time_in_hours
        )
        worked_time_in_seconds = group.total_work_duration
        extra = dict(
            night_work=night_work,
            max_work_range_in_hours=max_time_in_hours,
            work_range_in_seconds=worked_time_in_seconds,
            work_range_start=group.start_time.isoformat(),
            work_range_end=group.end_time.isoformat(),
        )
        if worked_time_in_seconds > max_time_in_hours * HOUR:
            extra["sanction_code"] = (
                NATINF_32083 if night_work else NATINF_11292
            )
            return ComputationResult(success=False, extra=extra)

    return ComputationResult(success=True, extra=extra)


def check_min_work_day_break(activity_groups, regulation_check, business):

    dict_variables = resolve_variables(regulation_check.variables, business)
    MINIMUM_DURATION_INDIVIDUAL_BREAK_IN_MIN = dict_variables[
        "MINIMUM_DURATION_INDIVIDUAL_BREAK_IN_MIN"
    ]
    MINIMUM_DURATION_WORK_IN_HOURS_1 = dict_variables[
        "MINIMUM_DURATION_WORK_IN_HOURS_1"
    ]
    MINIMUM_DURATION_WORK_IN_HOURS_2 = dict_variables[
        "MINIMUM_DURATION_WORK_IN_HOURS_2"
    ]
    MINIMUM_DURATION_BREAK_IN_MIN_1 = dict_variables[
        "MINIMUM_DURATION_BREAK_IN_MIN_1"
    ]
    MINIMUM_DURATION_BREAK_IN_MIN_2 = dict_variables[
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
        extra = dict(
            total_break_time_in_seconds=total_break_time_s,
            work_range_in_seconds=total_work_duration_s,
            work_range_start=activity_groups[0].start_time.isoformat(),
            sanction_code=SANCTION_CODE,
        )
        if latest_work_time is not None:
            extra["work_range_end"] = latest_work_time.isoformat()

        if (
            total_work_duration_s <= MINIMUM_DURATION_WORK_IN_HOURS_2 * HOUR
            and total_break_time_s < MINIMUM_DURATION_BREAK_IN_MIN_1 * MINUTE
        ):
            extra[
                "min_break_time_in_minutes"
            ] = MINIMUM_DURATION_BREAK_IN_MIN_1
            return ComputationResult(
                success=False,
                extra=extra,
            )
        elif (
            total_work_duration_s > MINIMUM_DURATION_WORK_IN_HOURS_2 * HOUR
            and total_break_time_s < MINIMUM_DURATION_BREAK_IN_MIN_2 * MINUTE
        ):
            extra[
                "min_break_time_in_minutes"
            ] = MINIMUM_DURATION_BREAK_IN_MIN_2
            return ComputationResult(
                success=False,
                extra=extra,
            )

    return ComputationResult(success=True)


def check_max_uninterrupted_work_time(
    activity_groups, regulation_check, business
):

    dict_variables = resolve_variables(regulation_check.variables, business)
    MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS = dict_variables[
        "MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS"
    ]

    # exit loop if we find a consecutive series of activites with span time > MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK
    now = datetime.now()
    current_uninterrupted_work_duration = 0
    current_uninterrupted_start = None
    latest_work_time = None
    extra = dict(
        max_uninterrupted_work_in_hours=MAXIMUM_DURATION_OF_UNINTERRUPTED_WORK_IN_HOURS
    )
    activity_ids_already_seen = set()

    for group in activity_groups:
        for activity in group.activities:
            if activity.id in activity_ids_already_seen:
                continue
            else:
                activity_ids_already_seen.add(activity.id)

            if activity.type is ActivityType.TRANSFER:
                continue
            if (
                latest_work_time is None
                or activity.start_time > latest_work_time
            ):
                current_uninterrupted_work_duration = 0
                current_uninterrupted_start = activity.start_time
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
                extra[
                    "longest_uninterrupted_work_in_seconds"
                ] = current_uninterrupted_work_duration
                extra[
                    "longest_uninterrupted_work_start"
                ] = current_uninterrupted_start.isoformat()
                extra["longest_uninterrupted_work_end"] = end_time.isoformat()
                extra["sanction_code"] = SANCTION_CODE
                return ComputationResult(success=False, extra=extra)
            latest_work_time = activity.end_time

    return ComputationResult(success=True, extra=extra)


DAILY_REGULATION_CHECKS = {
    RegulationCheckType.MINIMUM_DAILY_REST: [
        check_min_daily_rest,
        filter_work_days_to_current_and_next_day,
    ],
    RegulationCheckType.MAXIMUM_WORK_DAY_TIME: [
        lambda activity_groups, regulation_check, _, business: check_max_work_day_time(
            activity_groups, regulation_check, business
        ),
        filter_work_days_to_current_day,
    ],
    RegulationCheckType.MINIMUM_WORK_DAY_BREAK: [
        lambda activity_groups, regulation_check, _, business: check_min_work_day_break(
            activity_groups, regulation_check, business
        ),
        filter_work_days_to_current_day,
    ],
    RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME: [
        lambda activity_groups, regulation_check, _, business: check_max_uninterrupted_work_time(
            activity_groups, regulation_check, business
        ),
        filter_work_days_to_current_day,
    ],
}
