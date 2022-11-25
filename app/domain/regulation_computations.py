import datetime
from itertools import groupby

from sqlalchemy import func

from app.helpers.time import get_first_day_of_week
from app.models import RegulationComputation
from app.models.regulation_check import UnitType


def get_regulation_computations(
    user_id, start_date, end_date, submitter_type=None, grouped_by_unit=None
):
    base_query = RegulationComputation.query.filter(
        RegulationComputation.user_id == user_id,
        RegulationComputation.day >= start_date,
        RegulationComputation.day <= end_date,
    )
    if submitter_type:
        base_query = base_query.filter(
            RegulationComputation.submitter_type == submitter_type
        )

    # TODO: filter to get only where day is start of week
    # if grouped_by_unit == UnitType.WEEK:
    #     base_query = base_query.filter(
    #         func.da(RegulationComputation.day, 'D') == 7
    #     )

    regulation_computations = base_query.order_by(
        RegulationComputation.day
    ).all()

    if grouped_by_unit is None:
        return regulation_computations

    if grouped_by_unit == UnitType.WEEK:
        # print(list(regulation_computations)[0].day == get_first_day_of_week(list(regulation_computations)[0].day))
        regulation_computations = [
            rc
            for rc in regulation_computations
            if rc.day == get_first_day_of_week(rc.day)
        ]

    if grouped_by_unit == UnitType.DAY or grouped_by_unit == UnitType.WEEK:
        return {
            day_: list(computations_)
            for day_, computations_ in groupby(
                regulation_computations, lambda x: x.day
            )
        }

    raise ValueError(
        f"grouped_by_unit must be a value from app.models.regulation_check.UnitType"
    )
