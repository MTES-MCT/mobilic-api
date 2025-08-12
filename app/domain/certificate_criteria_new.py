import functools
import math
import multiprocessing
import time
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
from app.models.queries import query_activities
from app.models.regulation_check import RegulationCheckType, RegulationCheck

REAL_TIME_LOG_TOLERANCE_MINUTES = 60
REAL_TIME_LOG_MIN_ACTIVITY_LOGGED_IN_REAL_TIME_PER_MONTH_PERCENTAGE = 65
VALIDATION_MAX_DELAY_DAY = 7
VALIDATION_MIN_OK_PERCENTAGE = 65
COMPLIANCE_MAX_ALERTS_ALLOWED_PERCENTAGE = 0.8
CERTIFICATE_LIFETIME_MONTH = 2
CHANGES_MAX_CHANGES_PER_WEEK_PERCENTAGE = 10


def return_perf():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            return result, end - start

        return wrapper

    return decorator


def _filter_activities_on(activities):
    activities_on = [
        activity
        for activity in activities
        if activity.type != ActivityType.OFF
    ]
    return activities_on, len(activities_on)


@return_perf()
def compute_compliancy(company, start, end, nb_activities):

    users = company.users_between(start, end)
    nb_alert_types_ok = 0
    limit_nb_alerts = math.ceil(
        COMPLIANCE_MAX_ALERTS_ALLOWED_PERCENTAGE / 100.0 * nb_activities
    )

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

    enough_break_alerts = _get_alerts(
        users=users,
        start=start,
        end=end,
        type=RegulationCheckType.ENOUGH_BREAK,
        extra_field="not_enough_break",
    )
    uninterrupted_alerts = _get_alerts(
        users=users,
        start=start,
        end=end,
        type=RegulationCheckType.ENOUGH_BREAK,
        extra_field="too_much_uninterrupted_work_time",
    )

    for alerts in [enough_break_alerts, uninterrupted_alerts]:
        if len(alerts) < limit_nb_alerts:
            nb_alert_types_ok += 1

    return nb_alert_types_ok


@return_perf()
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


def _is_activity_in_real_time(activity):
    return (
        activity.creation_time - activity.start_time
    ).total_seconds() / 60.0 < REAL_TIME_LOG_TOLERANCE_MINUTES


@return_perf()
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


def print_stats(stats_dict):
    for st in ["real_time", "admin_changes", "compliancy"]:
        try:
            avg = math.fsum([s[st] for s in stats_dict.values()]) / len(
                stats_dict
            )
            max_ = max([s[st] for s in stats_dict.values()])
            print(f"-- {st.ljust(16)} Avg={avg:.4f}  Max={max_:.4f}")
        except:
            print(f"error while reading stat {st}")


def compute_company_certification(company_id, today, start, end):
    global stats, company_sizes, lock
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

    perfs = {}

    company = Company.query.filter(Company.id == company_id).one()

    # log_in_real_time, perf = compute_log_in_real_time(activity_ids)
    # perfs['real_time'] = perf
    #
    # admin_changes, perf = compute_admin_changes(
    #     company, start, end, activity_ids
    # )
    # perfs['admin_changes'] = perf

    compliancy, perf = compute_compliancy(
        company, start, end, len(activity_ids)
    )
    perfs["compliancy"] = perf
    company_sizes[company_id] = compliancy
    return
    expiration_date = certificate_expiration(today)

    with lock:
        stats[company_id] = perfs

    company_certification = CompanyCertificationNew.query.filter(
        CompanyCertificationNew.company == company,
        CompanyCertificationNew.attribution_date == today,
    ).first()

    company_certification.expiration_date = expiration_date
    company_certification.compliancy = compliancy
    company_certification.admin_changes = admin_changes
    company_certification.log_in_real_time = log_in_real_time

    # company_certification = CompanyCertificationNew(
    #     company=company,
    #     attribution_date=today,
    #     expiration_date=expiration_date,
    #     compliancy=compliancy,
    #     admin_changes=admin_changes,
    #     log_in_real_time=log_in_real_time,
    # )
    # db.session.add(company_certification)


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


def init_child(c, l, s, cs):
    global counter
    global lock
    global stats
    global company_sizes
    counter = c
    lock = l
    stats = s
    company_sizes = cs


def compute_company_certifications(today):
    # # Remove company certifications for attribution date
    # CompanyCertificationNew.query.filter(
    #     CompanyCertificationNew.attribution_date == today
    # ).delete()
    # db.session.commit()

    start, end = previous_month_period(today)

    companies = get_eligible_companies(start, end)
    company_ids = [c.id for c in companies]
    nb_eligible_companies = len(company_ids)
    app.logger.info(f"{nb_eligible_companies} eligible companies found")

    if nb_eligible_companies == 0:
        return

    db.session.close()
    db.engine.dispose()

    global total_tasks
    total_tasks = len(company_ids)

    c = multiprocessing.Value("i", 0)
    l = multiprocessing.Lock()
    stats = multiprocessing.Manager().dict()
    company_sizes = multiprocessing.Manager().dict()

    nb_forks = multiprocessing.cpu_count()
    with Pool(
        nb_forks, initializer=init_child, initargs=(c, l, stats, company_sizes)
    ) as p:
        func = functools.partial(
            run_compute_company_certification, today, start, end
        )
        p.map(func, company_ids)

    print_stats(stats)
    for c, v in company_sizes.items():
        print(f"{c}, {v}")


def run_compute_company_certification(today, start, end, company_id):
    global counter, lock

    with atomic_transaction(commit_at_end=True):
        try:
            compute_company_certification(
                company_id=company_id, today=today, start=start, end=end
            )
        except Exception as e:
            app.logger.error(f"Error with company {company_id}", exc_info=e)
        finally:
            with lock:
                counter.value += 1
                print(f"++ {counter.value}/{total_tasks} c_id={company_id}")
    db.session.close()
    db.engine.dispose()
