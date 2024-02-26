import functools
import math
import multiprocessing
from datetime import timedelta
from multiprocessing import Pool

from dateutil.relativedelta import relativedelta

from app import db, app
from app.controllers.utils import atomic_transaction
from app.helpers.time import end_of_month, previous_month_period, to_datetime
from app.models import RegulatoryAlert, Mission, Company, Activity
from app.models.activity import ActivityType
from app.models.company_certification import CompanyCertification
from app.models.queries import query_activities, query_company_missions
from app.models.regulation_check import RegulationCheckType

IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY = 2
IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH = 10
REAL_TIME_LOG_TOLERANCE_MINUTES = 60
REAL_TIME_LOG_MIN_ACTIVITY_LOGGED_IN_REAL_TIME_PER_MONTH_PERCENTAGE = 65
VALIDATION_MAX_DELAY_DAY = 7
VALIDATION_MIN_OK_PERCENTAGE = 65
COMPLIANCE_TOLERANCE_DAILY_REST_MINUTES = 15
COMPLIANCE_TOLERANCE_WORK_DAY_TIME_MINUTES = 15
COMPLIANCE_TOLERANCE_DAILY_BREAK_MINUTES = 5
COMPLIANCE_TOLERANCE_MAX_UNINTERRUPTED_WORK_TIME_MINUTES = 15
COMPLIANCE_MAX_ALERTS_ALLOWED_PERCENTAGE = 10
CERTIFICATE_LIFETIME_MONTH = 6
CHANGES_MAX_CHANGES_PER_WEEK_PERCENTAGE = 10


def is_employee_active(company, employee, start, end):
    activities = employee.query_activities_with_relations(
        start_time=start,
        end_time=end,
        restrict_to_company_ids=[company.id],
    ).all()

    nb_activity_per_day = {}
    active_days = set()
    for activity in activities:
        current_day = activity.start_time.date()
        last_day = activity.end_time.date() if activity.end_time else end
        while current_day <= last_day:
            if current_day in active_days:
                current_day += relativedelta(days=1)
                continue

            if activity.type == ActivityType.OFF:
                active_days.add(current_day)
                current_day += relativedelta(days=1)
                continue

            nb_activity_per_day[current_day] = (
                nb_activity_per_day.get(current_day, 0) + 1
            )
            if (
                nb_activity_per_day[current_day]
                >= IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY
            ):
                active_days.add(current_day)

            current_day += relativedelta(days=1)

        if len(active_days) >= IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH:
            return True
    return False


def are_at_least_n_employees_active(company, employees, start, end, n):
    nb_employees_active = 0
    for employee in employees:
        if is_employee_active(company, employee, start, end):
            nb_employees_active += 1
            if nb_employees_active == n:
                return True
    return False


def target_percentage_nb_drivers_active(nb_drivers):
    if nb_drivers <= 5:
        return 50
    return 60


def compute_be_active(company, start, end):
    employees = company.get_drivers(start, end)
    return are_at_least_n_employees_active(
        company,
        employees,
        start,
        end,
        math.ceil(
            target_percentage_nb_drivers_active(len(employees))
            / 100.0
            * len(employees)
        ),
    )


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
    activities_on = [
        activity
        for activity in activities
        if activity.type != ActivityType.OFF
    ]
    nb_total_activities = len(activities_on)
    if nb_total_activities == 0:
        return True

    limit_nb_activities = math.ceil(
        CHANGES_MAX_CHANGES_PER_WEEK_PERCENTAGE / 100.0 * nb_total_activities
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


def _is_mission_validated_soon_enough(mission, ok_period_start):
    mission_end_datetime = mission.ends[0].reception_time
    if mission_end_datetime.date() >= ok_period_start:
        return True

    first_validation_time_by_admin = mission.first_validation_time_by_admin()

    if not first_validation_time_by_admin:
        return False

    return first_validation_time_by_admin <= mission_end_datetime + timedelta(
        days=VALIDATION_MAX_DELAY_DAY
    )


def compute_validate_regularly(company, start, end):
    missions = query_company_missions(
        company_ids=[company.id],
        start_time=start,
        end_time=end,
        only_ended_missions=True,
    )
    missions = [mission.node for mission in missions.edges]

    nb_total_missions = len(missions)
    if nb_total_missions == 0:
        return True

    target_nb_missions_validated_soon_enough = math.ceil(
        nb_total_missions * VALIDATION_MIN_OK_PERCENTAGE / 100.0
    )

    # if a mission ends at this date or later, we will assume it is ok
    ok_period_start = end + timedelta(days=-(VALIDATION_MAX_DELAY_DAY - 1))

    nb_missions_validated_soon_enough = 0
    for mission in missions:
        if _is_mission_validated_soon_enough(mission, ok_period_start):
            nb_missions_validated_soon_enough += 1
        if (
            nb_missions_validated_soon_enough
            >= target_nb_missions_validated_soon_enough
        ):
            return True

    return False


def _is_activity_in_real_time(activity):
    return (
        activity.creation_time - activity.start_time
    ).total_seconds() / 60.0 < REAL_TIME_LOG_TOLERANCE_MINUTES


def compute_log_in_real_time(activities):
    activities_on = [
        activity
        for activity in activities
        if activity.type != ActivityType.OFF
    ]
    nb_activities = len(activities_on)
    if nb_activities == 0:
        return True

    target_nb_activities_in_real_time = math.ceil(
        REAL_TIME_LOG_MIN_ACTIVITY_LOGGED_IN_REAL_TIME_PER_MONTH_PERCENTAGE
        / 100.0
        * nb_activities
    )

    nb_activities_in_real_time = 0
    for activity in activities_on:
        if _is_activity_in_real_time(activity):
            nb_activities_in_real_time += 1
        if nb_activities_in_real_time >= target_nb_activities_in_real_time:
            return True

    return False


def certificate_expiration(today):
    expiration_month = today + relativedelta(
        months=+CERTIFICATE_LIFETIME_MONTH - 1
    )
    return end_of_month(expiration_month)


def compute_company_certification(company_id, today, start, end):
    activities = query_activities(
        include_dismissed_activities=False,
        start_time=start,
        end_time=end,
        company_ids=[company_id],
    ).all()
    company = Company.query.filter(Company.id == company_id).one()

    be_active = compute_be_active(company, start, end)
    be_compliant = compute_be_compliant(company, start, end, len(activities))
    not_too_many_changes = compute_not_too_many_changes(
        company, start, end, activities
    )
    validate_regularly = compute_validate_regularly(company, start, end)
    log_in_real_time = compute_log_in_real_time(activities)

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
