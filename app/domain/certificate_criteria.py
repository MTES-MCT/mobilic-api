import calendar
import datetime
import math
from datetime import date
from datetime import datetime
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from app import db
from app.models import User
from app.models.company_certification import CompanyCertification
from app.models.queries import query_activities, query_company_missions

IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY = 2
IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH = 10
IS_ACTIVE_COMPANY_SIZE_NB_EMPLOYEE_LIMIT = 3
IS_ACTIVE_MIN_EMPLOYEE_BIGGER_COMPANY_ACTIVE = 3
REAL_TIME_LOG_TOLERANCE_MINUTES = 15
REAL_TIME_LOG_MIN_ACTIVITY_LOGGED_IN_REAL_TIME_PER_MONTH_PERCENTAGE = 0.9
VALIDATION_MAX_DELAY_DAY = 7
VALIDATION_MIN_OK_PERCENTAGE = 0.9


def get_drivers(company, start, end):
    drivers = []
    users = company.users_between(start, end)
    for user in users:
        # a driver can have admin rights
        if user.has_admin_rights(
            company.id
        ) is False or user.first_activity_after(
            datetime.combine(start, datetime.min.time())
        ):
            drivers.append(user)
    return drivers


def is_employee_active(company, employee, start, end):

    activities = employee.query_activities_with_relations(
        start_time=start,
        end_time=end,
        restrict_to_company_ids=[company.id],
    ).all()

    nb_activity_per_day = {}
    for activity in activities:
        current_day = activity.start_time.date()
        last_day = activity.end_time.date() or end
        while current_day <= last_day:
            if current_day in nb_activity_per_day.keys():
                nb_activity_per_day[current_day] += 1
            else:
                nb_activity_per_day[current_day] = 1
            current_day += relativedelta(days=1)
        active_days = list(
            filter(
                lambda value: value >= IS_ACTIVE_MIN_NB_ACTIVITY_PER_DAY,
                nb_activity_per_day.values(),
            )
        )
        if len(active_days) >= IS_ACTIVE_MIN_NB_ACTIVE_DAY_PER_MONTH:
            return True
    return False


def are_all_employees_active(company, employees, start, end):
    if len(employees) == 0:
        return False

    for employee in employees:
        if not is_employee_active(company, employee, start, end):
            return False
    return True


def are_at_least_n_employees_active(company, employees, start, end, n):
    nb_employees_active = 0
    for employee in employees:
        if is_employee_active(company, employee, start, end):
            nb_employees_active += 1
            if nb_employees_active == n:
                return True
    return False


def compute_be_active(company, start, end):

    employees = get_drivers(company, start, end)

    if len(employees) < IS_ACTIVE_COMPANY_SIZE_NB_EMPLOYEE_LIMIT:
        return are_all_employees_active(company, employees, start, end)

    return are_at_least_n_employees_active(
        company,
        employees,
        start,
        end,
        IS_ACTIVE_MIN_EMPLOYEE_BIGGER_COMPANY_ACTIVE,
    )


def is_alert_above_tolerance_limit(regulatory_alert):
    # Repos journalier (on tolère jusqu'à 15 mn en moins)
    # Temps de pause (on tolère 5 mn de décalage avec le temps de pause min)
    # Repos hebdomadaire (pas de tolérance)
    # Durée du travail quotidien (on tolère jusqu'à 15 minutes de dépassement)
    # Durée maximale de travail ininterrompu (on tolère 15mn de dépassement)

    TOLERANCE_DAILY_REST_MINUTES = 15
    TOLERANCE_WORK_DAY_TIME_MINUTES = 15
    TOLERANCE_DAILY_BREAK_MINUTES = 5
    TOLERANCE_MAX_ININTERRUPTED_WORK_TIME_MINUTES = 15

    # si regulatory_alert.regulation_check.type = minimumDailyRest
    #   return extra.min_daily_break_in_hours - extra.breach_period_max_break_in_seconds > TOLERANCE_DAILY_REST_MINUTES
    # sinon si = maximumWorkDayTime
    #   return extra.work_range_in_seconds - extra.max_work_range_in_hours > TOLERANCE_WORK_DAY_TIME_MINUTES
    # sinon si = minimumWorkDayBreak
    #   return extra.total_break_time_in_seconds - extra.min_break_time_in_minutes > TOLERANCE_DAILY_BREAK_MINUTES
    # sinon si = maximumUninterruptedWorkTime
    #   return longest_uninterrupted_work_in_seconds - max_uninterrupted_work_in_hours > TOLERANCE_MAX_ININTERRUPTED_WORK_TIME_MINUTES
    return True


def compute_be_compliant(company, start, end):
    # pour chaque employé
    #   pour chaque regulatory_alert (use latest version)
    #     si is_alert_above_tolerance_limit(regulatory_alert)
    #       return False

    return True


def _has_activity_been_changed(activity, company_id):
    activity_user_id = activity.user_id
    # should we check if submitter was admin at the time ?
    version_author_ids = [
        version.submitter_id
        for version in activity.versions
        if version.submitter_id != activity_user_id
        and User.query.get(version.submitter_id).has_admin_rights(company_id)
    ]
    return len(version_author_ids) > 0


def compute_not_too_many_changes(company, start, end):
    MAX_CHANGES_PER_WEEK_PERCENTAGE = 0.1

    activities = query_activities(
        include_dismissed_activities=False,
        start_time=start,
        end_time=end,
        company_ids=[company.id],
    )
    # should we include dismissed ? is a dismissal a change ?

    nb_total_activities = activities.count()
    if nb_total_activities == 0:
        return False

    limit_nb_activities = math.ceil(
        MAX_CHANGES_PER_WEEK_PERCENTAGE * nb_total_activities
    )

    modified_count = 0
    for activity in activities:
        if _has_activity_been_changed(
            activity=activity, company_id=company.id
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

    return first_validation_time_by_admin <= mission.ends[
        0
    ].reception_time + timedelta(days=VALIDATION_MAX_DELAY_DAY)


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
        return False

    # if a mission ends at this date or later, we will assume it is ok
    ok_period_start = end + timedelta(days=-(VALIDATION_MAX_DELAY_DAY - 1))

    nb_missions_validated_soon_enough = len(
        [
            mission
            for mission in missions
            if _is_mission_validated_soon_enough(mission, ok_period_start)
        ]
    )

    return (
        nb_missions_validated_soon_enough / nb_total_missions
        >= VALIDATION_MIN_OK_PERCENTAGE
    )


def _is_activity_in_real_time(activity):
    return (
        activity.reception_time - activity.start_time
    ).total_seconds() / 60.0 < REAL_TIME_LOG_TOLERANCE_MINUTES


def compute_log_in_real_time(company, start, end):

    # Quid d'une activity modifiee a posteriori ?

    activities = query_activities(
        include_dismissed_activities=False,
        start_time=start,
        end_time=end,
        company_ids=[company.id],
    )

    nb_activities = activities.count()
    if nb_activities == 0:
        return False

    nb_activities_in_real_time = len(
        [
            activity
            for activity in activities
            if _is_activity_in_real_time(activity)
        ]
    )

    return (
        nb_activities_in_real_time / nb_activities
        >= REAL_TIME_LOG_MIN_ACTIVITY_LOGGED_IN_REAL_TIME_PER_MONTH_PERCENTAGE
    )


def end_of_month(date):
    return date.replace(day=calendar.monthrange(date.year, date.month)[1])


def previous_month_period(today):
    previous_month = today + relativedelta(months=-1)
    start = previous_month.replace(day=1)
    end = end_of_month(previous_month)
    return start, end


def certificate_expiration(today, lifetime_month):
    expiration_month = today + relativedelta(months=+lifetime_month - 1)
    return end_of_month(expiration_month)


def compute_company_certification(company):
    CERTIFICATE_LIFETIME_MONTH = 6

    today = date.today()
    start, end = previous_month_period(today)

    be_active = compute_be_active(company, start, end)
    be_compliant = compute_be_compliant(company, start, end)
    not_too_many_changes = compute_not_too_many_changes(company, start, end)
    validate_regularly = compute_validate_regularly(company, start, end)
    log_in_real_time = compute_log_in_real_time(company, start, end)

    certified = (
        be_active
        and be_compliant
        and not_too_many_changes
        and validate_regularly
        and log_in_real_time
    )
    expiration_date = (
        certificate_expiration(today, CERTIFICATE_LIFETIME_MONTH)
        if certified
        else None
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


def compute_company_certifications_if_needed():
    # TODO: select eligible companies : at least one mission non dismissed with creation_time in past month
    companies = []
    for company in companies:
        compute_company_certification(company)
