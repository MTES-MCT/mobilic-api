from itertools import groupby

from app.data_access.regulation_computation import (
    CompanyAdminRegulationComputationsByUserAndDay,
)
from app.helpers.submitter_type import SubmitterType
from app.models import RegulationComputation, RegulatoryAlert, RegulationCheck
from app.models.regulation_check import UnitType, RegulationCheckType


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


def get_regulatory_computations(user_id, start_date=None, end_date=None):
    return (
        RegulationComputation.query.filter(
            RegulationComputation.user_id == user_id,
            RegulationComputation.day.between(start_date, end_date),
        )
        .order_by(RegulationComputation.creation_time)
        .all()
    )


def get_admin_regulatory_computations_for_users(
    user_ids, from_date=None, to_date=None
):
    regulation_computations_query = RegulationComputation.query.filter(
        RegulationComputation.user_id.in_(user_ids),
        RegulationComputation.submitter_type == SubmitterType.ADMIN,
    )
    if from_date:
        regulation_computations_query = regulation_computations_query.filter(
            RegulationComputation.day >= from_date
        )
    if to_date:
        regulation_computations_query = regulation_computations_query.filter(
            RegulationComputation.day <= to_date
        )
    return regulation_computations_query.all()


def get_company_admin_regulation_computations(
    user_ids, from_date=None, to_date=None
):
    regulation_computations = get_admin_regulatory_computations_for_users(
        user_ids=user_ids, from_date=from_date, to_date=to_date
    )

    def _get_alerts_dict(unit):
        query = RegulatoryAlert.query.join(RegulationCheck).filter(
            RegulatoryAlert.user_id.in_(user_ids),
            RegulatoryAlert.submitter_type == SubmitterType.ADMIN,
            RegulationCheck.unit == unit,
        )
        if from_date:
            query = query.filter(RegulatoryAlert.day >= from_date)
        if to_date:
            query = query.filter(RegulatoryAlert.day <= to_date)
        alerts = query.all()
        alerts_dict = {}
        for a in alerts:
            alerts_dict.setdefault((a.user_id, a.day), []).append(a)
        return alerts_dict

    daily_alerts = _get_alerts_dict(UnitType.DAY)
    weekly_alerts = _get_alerts_dict(UnitType.WEEK)

    ret = []
    for rc in regulation_computations:
        day = rc.day
        user_id = rc.user_id
        daily_alerts_for_user = daily_alerts.get((user_id, day), [])
        nb_alerts_daily_admin = 0
        for a in daily_alerts_for_user:
            if a.regulation_check.type == RegulationCheckType.ENOUGH_BREAK:
                if a.extra["too_much_uninterrupted_work_time"]:
                    nb_alerts_daily_admin += 1
                if a.extra["not_enough_break"]:
                    nb_alerts_daily_admin += 1
            else:
                nb_alerts_daily_admin += 1

        weekly_alerts_for_user = weekly_alerts.get((user_id, day), [])
        nb_alerts_weekly_admin = len(weekly_alerts_for_user)

        ret.append(
            CompanyAdminRegulationComputationsByUserAndDay(
                day=day,
                user_id=user_id,
                nb_alerts_daily_admin=nb_alerts_daily_admin,
                nb_alerts_weekly_admin=nb_alerts_weekly_admin,
            )
        )

    return ret
