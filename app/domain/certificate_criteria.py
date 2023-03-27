import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from app import db
from app.models.company_certification import CompanyCertification


def get_drivers(company, start, end):
    drivers = []
    users = company.users_between(start, end)
    for user in users:
        # a driver can have admin rights
        if user.has_admin_rights(
            company
        ) is False or user.first_activity_after(start):
            drivers.append(user)
    return drivers


def is_employee_active(company, employee, start, end):
    MIN_NB_ACTIVITY_PER_DAY = 2
    MIN_NB_ACTIVE_DAY_PER_MONTH = 10

    activities = employee.query_activities_with_relations(
        start_time=start,
        end_time=end,
        restrict_to_company_ids=[company.id],
    ).all()

    nb_activity_per_day = {}
    for activity in activities:
        current_day = activity.start_time
        last_day = activity.end_time or end
        while current_day <= last_day:
            if current_day in nb_activity_per_day.keys():
                nb_activity_per_day[current_day] += 1
            else:
                nb_activity_per_day[current_day] = 1
            current_day += relativedelta(days=1)
        active_days = list(
            filter(
                lambda value: value >= MIN_NB_ACTIVITY_PER_DAY,
                nb_activity_per_day.values(),
            )
        )
        if len(active_days) >= MIN_NB_ACTIVE_DAY_PER_MONTH:
            return True
    return False


def are_all_employees_active(company, employees, start, end):
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
    COMPANY_SIZE_NB_EMPLOYEE_LIMIT = 3
    MIN_EMPLOYEE_BIGGER_COMPANY_ACTIVE = 3

    employees = get_drivers(company, start, end)

    if len(employees) < COMPANY_SIZE_NB_EMPLOYEE_LIMIT:
        return are_all_employees_active(company, employees, start, end)

    return are_at_least_n_employees_active(
        company,
        employees,
        start,
        end,
        MIN_EMPLOYEE_BIGGER_COMPANY_ACTIVE,
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


def compute_not_too_many_changes(company, start, end):
    # Nombre de modifications ne dépassant pas 10% des saisies à la semaine (côté gestionnaire)
    MAX_CHANGES_PER_WEEK_PERCENTAGE = 0.1

    # count_all_activities = nb activity for company in month
    # limit = count_all_activities * MAX_CHANGES_PER_WEEK_PERCENTAGE
    # pour chacune de ces activity:
    #   si activity.user <> activity_version.submitter
    #    et employment(company, submitter) en cours has_admin_right = True
    #     count_updated_activities += 1
    #     si count_updated_activities > limit
    #       return False

    return True


def compute_validate_regularly(company, start, end):
    # Validation régulière de la part du gestionnaire
    MAX_VALIDATION_DELAY_DAY = 7
    MIN_VALIDATION_OK_PERCENTAGE = 0.9

    # missions = missions de l'entreprise du mois passé
    # pour toutes les missions
    #   si
    #     - pas de validation et date fin < fin du mois précédent - MAX_VALIDATION_DELAY_DAY
    #     - ou date validation - date fin > MAX_VALIDATION_DELAY_DAY
    #      count_validation_ok += 1
    # si count_validation_ok / len(missions) < MIN_VALIDATION_OK_PERCENTAGE
    #   return False

    return True


def compute_log_in_real_time(company, start, end):
    # sur l'intégralité des activités saisies dans le mois pour l'entreprise,
    # au moins 90% de "temps réel" ( = saisie à moins de 15mn du début de l'activité)
    TOLERANCE_REAL_TIME_LOG_MINUTES = 15
    MIN_ACTIVITY_LOGGED_IN_REAL_TIME_PER_MONTH_PERCENTAGE = 0.9

    # nb_temps_reel = 0
    # pour chaque activity
    # - non dismissed
    # - pour une mission de cette company
    # - avec start_time le mois précédent
    #   nb_temps_reel += 1 si creation_time - start_time > TOLERANCE_REAL_TIME_LOG_MINUTES sinon 0

    # si nb_temps_reel / nb_activity > MIN_ACTIVITY_LOGGED_IN_REAL_TIME_PER_MONTH_PERCENTAGE
    #   return True

    return False


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
