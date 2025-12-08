from dateutil.relativedelta import relativedelta

from app.data_access.regulation_computation import (
    get_regulation_checks_by_unit,
)
from app.data_access.regulatory_alerts_summary import (
    AlertsGroup,
    RegulatoryAlertsSummary,
)
from app.domain.regulations_per_day import (
    EXTRA_NOT_ENOUGH_BREAK,
    EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME,
)
from app.helpers.submitter_type import SubmitterType
from app.models import RegulatoryAlert
from app.models.regulation_check import UnitType, RegulationCheckType


def query_alerts_for_month(month, user_ids):
    def query_alerts(_start_date, _end_date, _user_ids, count_only=True):
        query = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id.in_(_user_ids),
            RegulatoryAlert.day >= _start_date,
            RegulatoryAlert.day < _end_date,
            RegulatoryAlert.submitter_type == SubmitterType.ADMIN,
        )
        if count_only:
            base_count = query.count()
            double_alerts_count = query.filter(
                RegulatoryAlert.extra[EXTRA_NOT_ENOUGH_BREAK].as_boolean()
                == True,
                RegulatoryAlert.extra[
                    EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME
                ].as_boolean()
                == True,
            ).count()
            return base_count + double_alerts_count
        return query.all()

    start_date = month
    end_date = month + relativedelta(months=1)

    current_month_alerts = query_alerts(
        _start_date=start_date,
        _end_date=end_date,
        _user_ids=user_ids,
        count_only=False,
    )
    previous_start = month + relativedelta(months=-1)
    previous_month_alerts_count = query_alerts(
        _start_date=previous_start,
        _end_date=start_date,
        _user_ids=user_ids,
    )
    return current_month_alerts, previous_month_alerts_count


def get_regulatory_alerts_summary(month, user_ids, unique_user_id=False):
    current_month_alerts, previous_month_alerts_count = query_alerts_for_month(
        month=month, user_ids=user_ids
    )

    start_date = month
    daily_checks = get_regulation_checks_by_unit(unit=UnitType.DAY)
    daily_alerts = {}

    def _append_alerts(alerts, type):
        if type in daily_alerts:
            daily_alerts[type].nb_alerts += len(alerts)
            if unique_user_id:
                daily_alerts[type].days += [a.day for a in alerts]
        else:
            daily_alerts[type] = AlertsGroup(
                alerts_type=type,
                nb_alerts=len(alerts),
                days=[a.day for a in alerts] if unique_user_id else [],
            )

    for check in daily_checks:
        if check.type == RegulationCheckType.NO_LIC:
            continue

        alerts = [
            a
            for a in current_month_alerts
            if a.regulation_check_id == check.id
        ]
        if check.type == RegulationCheckType.ENOUGH_BREAK:
            for extra_field in [
                EXTRA_NOT_ENOUGH_BREAK,
                EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME,
            ]:
                extra_alerts = [a for a in alerts if a.extra[extra_field]]
                _append_alerts(alerts=extra_alerts, type=extra_field)
            continue

        if check.type == RegulationCheckType.MINIMUM_WORK_DAY_BREAK:
            _append_alerts(alerts=alerts, type=EXTRA_NOT_ENOUGH_BREAK)
            continue
        if check.type == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME:
            _append_alerts(
                alerts=alerts, type=EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME
            )
            continue
        _append_alerts(alerts=alerts, type=check.type)

    weekly_checks = get_regulation_checks_by_unit(
        unit=UnitType.WEEK, date=start_date
    )
    weekly_alerts = []
    for check in weekly_checks:
        alerts = [
            a
            for a in current_month_alerts
            if a.regulation_check_id == check.id
        ]
        weekly_alerts.append(
            AlertsGroup(
                alerts_type=check.type,
                nb_alerts=len(alerts),
                days=[],
            )
        )

    # alerts with too_much_uninterrupted_work_time=True and not_enough_break=True count double
    double_alerts_to_add = len(
        [
            a
            for a in current_month_alerts
            if a.extra.get(EXTRA_TOO_MUCH_UNINTERRUPTED_WORK_TIME, False)
            and a.extra.get(EXTRA_NOT_ENOUGH_BREAK, False)
        ]
    )

    return RegulatoryAlertsSummary(
        month=month,
        total_nb_alerts=len(current_month_alerts) + double_alerts_to_add,
        total_nb_alerts_previous_month=previous_month_alerts_count,
        daily_alerts=daily_alerts.values(),
        weekly_alerts=weekly_alerts,
    )
