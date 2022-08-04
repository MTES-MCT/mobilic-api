import json

from app import db
from app.helpers.errors import InvalidResourceError
from app.helpers.regulations_utils import HOUR, ComputationResult
from app.models.regulation_check import RegulationCheck, RegulationCheckType
from app.models.regulatory_alert import RegulatoryAlert
from sqlalchemy import desc


def compute_regulations_per_week(user, week, submitter_type):

    for type, computation in WEEKLY_REGULATION_CHECKS.items():
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


WEEKLY_REGULATION_CHECKS = {
    RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK: check_max_worked_day_in_week,
}
