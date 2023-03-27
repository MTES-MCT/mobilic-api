from datetime import datetime

from dateutil.relativedelta import relativedelta

from app import db
from app.models.company_certification import CompanyCertification


def is_employee_active(company, employee):
    MIN_NB_ACTIVITY_PER_DAY = 2
    MIN_NB_ACTIVE_DAY_PER_MONTH = 10

    # active_days = select all activities
    # - non dismissed
    # - de l'employé
    # - pour une mission de cette company
    # - avec start_time le mois précédent
    # group by day
    # having count >= MIN_NB_ACTIVITY_PER_DAY

    # si nb active_days >= MIN_NB_ACTIVE_DAY_PER_MONTH
    #    return True

    return False


def be_active(company):
    # si <= 3 salariés : 75% des salariés de l’entreprise sont “actifs”
    # si > 3 salariés : au moins 3 salariés “actifs”
    # salariés “actifs” : nb jours avec au moins 2 activités >= 10 (dans le mois)
    COMPANY_SIZE_NB_EMPLOYEE_LIMIT = 3
    MIN_EMPLOYEE_BIGGER_COMPANY_ACTIVE = 3

    # nb employee actif = 0
    # si company nb employee = 1
    #   si is_employee_active(company, employee)
    #     return True
    # sinon si company nb employee <= COMPANY_SIZE_NB_EMPLOYEE_LIMIT
    #   pour chaque employee
    #     nb employee actif += 1 si is_employee_active(company, employee)
    #     si nb empoyee actif = 2
    #       return True
    # sinon
    #   pour chaque employee
    #     nb employee actif += 1 si is_employee_active(company, employee)
    #     si nb empoyee actif = MIN_EMPLOYEE_BIGGER_COMPANY_ACTIVE
    #       return True
    return False


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


def be_compliant(company):
    # pour chaque employé
    #   pour chaque regulatory_alert (use latest version)
    #     si is_alert_above_tolerance_limit(regulatory_alert)
    #       return False

    return True


def not_too_many_changes(company):
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


def validate_regularly(company):
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


def log_in_real_time(company):
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


def compute_company_certification(company):
    attribution_date = datetime.today()

    be_active = be_active(company)
    be_compliant = be_compliant(company)
    not_too_many_changes = not_too_many_changes(company)
    validate_regularly = validate_regularly(company)
    log_in_real_time = log_in_real_time(company)

    certified = (
        be_active
        and be_compliant
        and not_too_many_changes
        and validate_regularly
        and log_in_real_time
    )
    if certified:
        expiration_date = attribution_date + relativedelta(month=5, day=31)

    company_certification = CompanyCertification(
        company=company,
        attribution_date=attribution_date,
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
