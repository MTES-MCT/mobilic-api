import functools
import math
import multiprocessing
from multiprocessing import Pool

from dateutil.relativedelta import relativedelta
from sqlalchemy import func

from app import db, app
from app.controllers.utils import atomic_transaction
from app.helpers.time import end_of_month, previous_month_period, to_datetime
from app.models import RegulatoryAlert, Mission, Company, Activity
from app.models.activity import ActivityType
from app.models.company_certification import CompanyCertification
from app.models.queries import query_activities
from app.models.regulation_check import RegulationCheckType

REAL_TIME_LOG_TOLERANCE_MINUTES = 60
COMPLIANCE_TOLERANCE_DAILY_REST_MINUTES = 15
COMPLIANCE_TOLERANCE_WORK_DAY_TIME_MINUTES = 15
COMPLIANCE_TOLERANCE_DAILY_BREAK_MINUTES = 5
COMPLIANCE_TOLERANCE_MAX_UNINTERRUPTED_WORK_TIME_MINUTES = 15
COMPLIANCE_MAX_ALERTS_ALLOWED_PERCENTAGE = 10
CERTIFICATE_LIFETIME_MONTH = 2
CHANGES_MAX_CHANGES_PER_WEEK_PERCENTAGE = 10


def _filter_activities_on(activities):
    activities_on = [
        activity
        for activity in activities
        if activity.type != ActivityType.OFF
    ]
    return activities_on, len(activities_on)


def is_alert_above_tolerance_limit(regulatory_alert):
    if (
        regulatory_alert.regulation_check.type
        == RegulationCheckType.MINIMUM_DAILY_REST
    ):
        return (
            regulatory_alert.extra["min_daily_break_in_hours"] * 60
            - regulatory_alert.extra["breach_period_max_break_in_seconds"] / 60
            > COMPLIANCE_TOLERANCE_DAILY_REST_MINUTES
        )

    if (
        regulatory_alert.regulation_check.type
        == RegulationCheckType.MAXIMUM_WORK_DAY_TIME
    ):
        return (
            regulatory_alert.extra["work_range_in_seconds"] / 60
            - regulatory_alert.extra["max_work_range_in_hours"] * 60
            > COMPLIANCE_TOLERANCE_WORK_DAY_TIME_MINUTES
        )

    if (
        regulatory_alert.regulation_check.type
        == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
    ):
        return (
            regulatory_alert.extra["min_break_time_in_minutes"]
            - regulatory_alert.extra["total_break_time_in_seconds"] / 60
            > COMPLIANCE_TOLERANCE_DAILY_BREAK_MINUTES
        )

    if (
        regulatory_alert.regulation_check.type
        == RegulationCheckType.MAXIMUM_UNINTERRUPTED_WORK_TIME
    ):
        return (
            regulatory_alert.extra["longest_uninterrupted_work_in_seconds"]
            / 60
            - regulatory_alert.extra["max_uninterrupted_work_in_hours"] * 60
            > COMPLIANCE_TOLERANCE_MAX_UNINTERRUPTED_WORK_TIME_MINUTES
        )

    if (
        regulatory_alert.regulation_check.type
        == RegulationCheckType.MAXIMUM_WORKED_DAY_IN_WEEK
    ):
        return False

    return True


def compute_be_compliant(company, start, end, nb_activities):
    users = company.users_between(start, end)

    regulatory_alerts = RegulatoryAlert.query.filter(
        RegulatoryAlert.user_id.in_([user.id for user in users]),
        RegulatoryAlert.day >= start,
        RegulatoryAlert.day <= end,
    )
    limit_nb_alerts = math.ceil(
        COMPLIANCE_MAX_ALERTS_ALLOWED_PERCENTAGE / 100.0 * nb_activities
    )
    nb_alerts_above_limit = 0
    for regulatory_alert in regulatory_alerts:
        if is_alert_above_tolerance_limit(regulatory_alert):
            nb_alerts_above_limit += 1
        if nb_alerts_above_limit >= limit_nb_alerts:
            return False

    return True


def _has_activity_been_created_or_modified_by_an_admin(activity, admin_ids):
    activity_user_id = activity.user_id
    for version in activity.versions:
        if (
            version.submitter_id in admin_ids
            and version.submitter_id != activity_user_id
        ):
            return True
    return False


def compute_not_too_many_changes(company, start, end, activities):
    activities_on, nb_activities_on = _filter_activities_on(activities)

    if nb_activities_on == 0:
        return True

    limit_nb_activities = math.ceil(
        CHANGES_MAX_CHANGES_PER_WEEK_PERCENTAGE / 100.0 * nb_activities_on
    )

    company_admin_ids = [admin.id for admin in company.get_admins(start, end)]

    modified_count = 0
    for activity in activities_on:
        if _has_activity_been_created_or_modified_by_an_admin(
            activity=activity, admin_ids=company_admin_ids
        ):
            modified_count += 1
            if modified_count >= limit_nb_activities:
                return False

    return True


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
                    "epoch", Activity.creation_time - Activity.start_time
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

    be_active = True
    be_compliant = compute_be_compliant(company, start, end, len(activities))
    not_too_many_changes = compute_not_too_many_changes(
        company, start, end, activities
    )
    validate_regularly = True

    certified = (
        be_active
        and be_compliant
        and not_too_many_changes
        and validate_regularly
        and log_in_real_time
    )
    expiration_date = (
        certificate_expiration(today) if certified else end_of_month(today)
    )

    company_certification = CompanyCertification(
        company=company,
        attribution_date=today,
        expiration_date=expiration_date,
        be_active=be_active,
        be_compliant=be_compliant,
        not_too_many_changes=not_too_many_changes,
        validate_regularly=validate_regularly,
        log_in_real_time=log_in_real_time,
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
