from sqlalchemy import desc

from app import db
from app.domain.regulations_helper import resolve_variables
from app.helpers.errors import InvalidResourceError
from app.helpers.regulations_utils import HOUR, ComputationResult
from app.models.regulation_check import RegulationCheck, RegulationCheckType
from app.models.regulatory_alert import RegulatoryAlert

NATINF_13152 = "NATINF 13152"
NATINF_11289 = "NATINF 11289"


def compute_regulations_per_week(user, business, week, submitter_type):
    for type, computation in WEEKLY_REGULATION_CHECKS.items():
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

        success, extra = computation(week, regulation_check, business)

        if not success:
            regulatory_alert = RegulatoryAlert(
                day=week["start"],
                extra=extra,
                submitter_type=submitter_type,
                user=user,
                regulation_check_id=regulation_check.id,
                business=business,
            )
            db.session.add(regulatory_alert)


def check_max_worked_day_in_week(week, regulation_check, business):
    dict_variables = resolve_variables(regulation_check.variables, business)
    MAXIMUM_DAY_WORKED_BY_WEEK = dict_variables["MAXIMUM_DAY_WORKED_BY_WEEK"]
    MINIMUM_WEEKLY_BREAK_IN_HOURS = dict_variables[
        "MINIMUM_WEEKLY_BREAK_IN_HOURS"
    ]
    extra = dict(
        max_nb_days_worked_by_week=MAXIMUM_DAY_WORKED_BY_WEEK,
        min_weekly_break_in_hours=MINIMUM_WEEKLY_BREAK_IN_HOURS,
    )
    too_many_days = week["worked_days"] > MAXIMUM_DAY_WORKED_BY_WEEK
    not_enough_rest = (
        week["rest_duration_s"] < MINIMUM_WEEKLY_BREAK_IN_HOURS * HOUR
    )
    extra["too_many_days"] = too_many_days
    extra["sanction_code"] = NATINF_13152
    if not_enough_rest:
        extra["rest_duration_s"] = week["rest_duration_s"]

    success = not (too_many_days or not_enough_rest)
    return ComputationResult(success=success, extra=extra)


def check_max_work_in_calendar_week(week, regulation_check, business):
    dict_variables = resolve_variables(regulation_check.variables, business)
    MAXIMUM_WEEKLY_WORK_IN_HOURS = dict_variables[
        "MAXIMUM_WEEKLY_WORK_IN_HOURS"
    ]
    work_duration_in_seconds = week["work_duration_s"]
    extra = dict(
        max_weekly_work_in_seconds=MAXIMUM_WEEKLY_WORK_IN_HOURS * HOUR,
        work_duration_in_seconds=work_duration_in_seconds,
    )
    success = work_duration_in_seconds <= MAXIMUM_WEEKLY_WORK_IN_HOURS * HOUR
    if not success:
        extra["sanction_code"] = NATINF_11289

    if len(week["days"]) > 0:
        extra["work_range_start"] = week["days"][0]["start_time"].isoformat()
        extra["work_range_end"] = week["days"][-1]["end_time"].isoformat()

    return ComputationResult(success=success, extra=extra)


WEEKLY_REGULATION_CHECKS = {
    RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK: check_max_worked_day_in_week,
    RegulationCheckType.MAXIMUM_WORK_IN_CALENDAR_WEEK: check_max_work_in_calendar_week,
}
