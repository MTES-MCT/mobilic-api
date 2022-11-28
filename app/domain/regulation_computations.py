from itertools import groupby

from app.models import RegulationComputation


def get_regulation_computations(
    user_id, start_date, end_date, submitter_type=None, grouped_by_day=False
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

    regulation_computations = base_query.order_by(
        RegulationComputation.day
    ).all()

    if grouped_by_day:
        return {
            day_: list(computations_)
            for day_, computations_ in groupby(
                regulation_computations, lambda x: x.day
            )
        }

    return regulation_computations
