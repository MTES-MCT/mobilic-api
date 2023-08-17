from sqlalchemy import desc

from app import db
from app.helpers.errors import InvalidResourceError
from app.helpers.regulations_utils import HOUR, ComputationResult
from app.models.regulation_check import RegulationCheck, RegulationCheckType
from app.models.regulatory_alert import RegulatoryAlert

NATINF_13152 = "NATINF 13152"


def compute_regulations_per_week(user, week, submitter_type):

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

        success, extra = computation(week, regulation_check)

        if not success:
            regulatory_alert = RegulatoryAlert(
                day=week["start"],
                extra=extra,
                submitter_type=submitter_type,
                user=user,
                regulation_check_id=regulation_check.id,
            )
            db.session.add(regulatory_alert)


def check_max_worked_day_in_week(week, regulation_check):
    MAXIMUM_DAY_WORKED_BY_WEEK = regulation_check.variables[
        "MAXIMUM_DAY_WORKED_BY_WEEK"
    ]
    MINIMUM_WEEKLY_BREAK_IN_HOURS = regulation_check.variables[
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


WEEKLY_REGULATION_CHECKS = {
    RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK: check_max_worked_day_in_week,
}
