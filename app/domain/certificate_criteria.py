import functools
import math
import multiprocessing
from multiprocessing import Pool

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, distinct

from app import db, app
from app.controllers.utils import atomic_transaction
from app.helpers.time import end_of_month, previous_month_period, to_datetime
from app.models import (
    RegulatoryAlert,
    Mission,
    Company,
    Activity,
    ActivityVersion,
)
from app.models.activity import ActivityType
from app.models.company_certification import CompanyCertification
from app.models.queries import query_activities
from app.models.regulation_check import RegulationCheckType, RegulationCheck

REAL_TIME_LOG_TOLERANCE_MINUTES = 60
COMPLIANCE_MAX_ALERTS_ALLOWED_PERCENTAGE = 0.5
CERTIFICATE_LIFETIME_MONTH = 2


def compute_compliancy(company, start, end, nb_activities):
    users = company.users_between(start, end)
    nb_alert_types_ok = 0
    limit_nb_alerts = math.ceil(
        COMPLIANCE_MAX_ALERTS_ALLOWED_PERCENTAGE / 100.0 * nb_activities
    )
    info_alerts = []

    def _get_alerts(users, start, end, type, extra_field=None):
        query = RegulatoryAlert.query.filter(
            RegulatoryAlert.user_id.in_([user.id for user in users]),
            RegulatoryAlert.day >= start,
            RegulatoryAlert.day <= end,
            RegulatoryAlert.regulation_check.has(RegulationCheck.type == type),
        )
        if extra_field:
            query = query.filter(
                RegulatoryAlert.extra[extra_field].as_boolean() == True
            )
        return query.all()

    for type in [
        RegulationCheckType.MINIMUM_DAILY_REST,
        RegulationCheckType.MAXIMUM_WORK_DAY_TIME,
        RegulationCheckType.MAXIMUM_WORK_IN_CALENDAR_WEEK,
        RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK,
    ]:
        regulatory_alerts = _get_alerts(
            users=users, start=start, end=end, type=type
        )
        if len(regulatory_alerts) < limit_nb_alerts:
            nb_alert_types_ok += 1
        else:
            info_alerts.append({"type": type})

    for extra_field in [
        "not_enough_break",
        "too_much_uninterrupted_work_time",
    ]:
        _alerts = _get_alerts(
            users=users,
            start=start,
            end=end,
            type=RegulationCheckType.ENOUGH_BREAK,
            extra_field=extra_field,
        )
        if len(_alerts) < limit_nb_alerts:
            nb_alert_types_ok += 1
        else:
            info_alerts.append(
                {
                    "type": RegulationCheckType.ENOUGH_BREAK,
                    "extra_field": extra_field,
                }
            )

    return nb_alert_types_ok, info_alerts


def compute_admin_changes(company, start, end, activity_ids):
    if len(activity_ids) == 0:
        return 0.0

    company_admin_ids = [admin.id for admin in company.get_admins(start, end)]

    modified_count = (
        db.session.query(func.count(distinct(Activity.id)))
        .join(ActivityVersion, ActivityVersion.activity_id == Activity.id)
        .filter(
            Activity.id.in_(activity_ids),
            ActivityVersion.submitter_id.in_(company_admin_ids),
            ActivityVersion.submitter_id != Activity.user_id,
        )
        .scalar()
    )
    return modified_count / len(activity_ids)


def compute_log_in_real_time(activity_ids):
    if len(activity_ids) == 0:
        return 1.0

    tolerance_in_seconds = REAL_TIME_LOG_TOLERANCE_MINUTES * 60

    nb_in_real_time = (
        db.session.query(func.count(Activity.id))
        .filter(
            Activity.id.in_(activity_ids),
            (
                func.extract(
                    "epoch", Activity.reception_time - Activity.start_time
                )
            )
            < tolerance_in_seconds,
        )
        .scalar()
    )
    return nb_in_real_time / len(activity_ids)


def certificate_expiration(today):
    expiration_month = today + relativedelta(
        months=+CERTIFICATE_LIFETIME_MONTH - 1
    )
    return end_of_month(expiration_month)


def compute_company_certification(company_id, today, start, end):
    query = (
        query_activities(
            include_dismissed_activities=False,
            start_time=start,
            end_time=end,
            company_ids=[company_id],
        )
        .filter(Activity.type != ActivityType.OFF)
        .with_entities(Activity.id)
    )
    activity_ids = [a[0] for a in query.all()]

    company = Company.query.filter(Company.id == company_id).one()

    log_in_real_time = compute_log_in_real_time(activity_ids)
    admin_changes = compute_admin_changes(company, start, end, activity_ids)
    compliancy, info_alerts = compute_compliancy(
        company, start, end, len(activity_ids)
    )

    expiration_date = certificate_expiration(today)

    company_certification = CompanyCertification(
        company=company,
        attribution_date=today,
        expiration_date=expiration_date,
        compliancy=compliancy,
        admin_changes=admin_changes,
        log_in_real_time=log_in_real_time,
        info={"alerts": info_alerts},
    )
    db.session.add(company_certification)


# returns companies with missions created during period with non-dismissed activities
def get_eligible_companies(start, end):
    missions_subquery = (
        Mission.query.join(Activity, Activity.mission_id == Mission.id)
        .filter(
            Mission.creation_time >= to_datetime(start),
            Mission.creation_time <= to_datetime(end, date_as_end_of_day=True),
        )
        .filter(~Activity.is_dismissed)
        .with_entities(Mission.company_id)
        .distinct()
        .subquery()
    )

    return Company.query.filter(Company.id.in_(missions_subquery)).all()


def compute_company_certifications(today):
    # Remove company certifications for attribution date
    CompanyCertification.query.filter(
        CompanyCertification.attribution_date == today
    ).delete()
    db.session.commit()

    start, end = previous_month_period(today)

    companies = get_eligible_companies(start, end)
    company_ids = [c.id for c in companies]
    nb_eligible_companies = len(company_ids)
    app.logger.info(f"{nb_eligible_companies} eligible companies found")

    if nb_eligible_companies == 0:
        return

    db.session.close()
    db.engine.dispose()

    nb_forks = multiprocessing.cpu_count()
    with Pool(nb_forks) as p:
        func = functools.partial(
            run_compute_company_certification, today, start, end
        )
        p.map(func, company_ids)


def run_compute_company_certification(today, start, end, company_id):
    with atomic_transaction(commit_at_end=True):
        try:
            compute_company_certification(
                company_id=company_id, today=today, start=start, end=end
            )
        except Exception as e:
            app.logger.error(f"Error with company {company_id}", exc_info=e)
    db.session.close()
    db.engine.dispose()
