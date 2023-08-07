from itertools import groupby

from app.models import RegulationComputation, RegulatoryAlert


def get_regulation_computations(
    user_id,
    start_date=None,
    end_date=None,
    submitter_type=None,
    grouped_by_day=False,
):
    base_query = RegulationComputation.query.filter(
        RegulationComputation.user_id == user_id
    )
    if start_date:
        base_query = base_query.filter(RegulationComputation.day >= start_date)
    if end_date:
        base_query = base_query.filter(RegulationComputation.day <= end_date)
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


def get_regulatory_alerts(user_id, start_date=None, end_date=None):
    return RegulatoryAlert.query.filter(
        RegulatoryAlert.user_id == user_id,
        RegulatoryAlert.day.between(start_date, end_date),
    ).all()
