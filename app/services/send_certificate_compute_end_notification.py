from sqlalchemy import func
from sqlalchemy.sql.functions import now
from dateutil.relativedelta import relativedelta
from datetime import date

from app import db
from app.helpers.mattermost import send_mattermost_message
from app.models import CompanyCertification
from app.models.company_certification import CertificationLevel


def send_certificate_compute_end_notification():
    nb_certified_companies = (
        db.session.query(CompanyCertification.company_id)
        .filter(
            CompanyCertification.certification_level_int > 0,
            CompanyCertification.expiration_date > now(),
            CompanyCertification.log_in_real_time != None,
            CompanyCertification.admin_changes != None,
            CompanyCertification.compliancy != None,
        )
        .distinct()
        .count()
    )

    nb_bronze_companies = (
        db.session.query(CompanyCertification.company_id)
        .filter(
            CompanyCertification.certification_level_int
            == CertificationLevel.BRONZE,
            CompanyCertification.expiration_date > now(),
        )
        .distinct()
        .count()
    )

    nb_silver_companies = (
        db.session.query(CompanyCertification.company_id)
        .filter(
            CompanyCertification.certification_level_int
            == CertificationLevel.SILVER,
            CompanyCertification.expiration_date > now(),
        )
        .distinct()
        .count()
    )

    nb_gold_companies = (
        db.session.query(CompanyCertification.company_id)
        .filter(
            CompanyCertification.certification_level_int
            == CertificationLevel.GOLD,
            CompanyCertification.expiration_date > now(),
        )
        .distinct()
        .count()
    )

    nb_diamond_companies = (
        db.session.query(CompanyCertification.company_id)
        .filter(
            CompanyCertification.certification_level_int
            == CertificationLevel.DIAMOND,
            CompanyCertification.expiration_date > now(),
        )
        .distinct()
        .count()
    )

    today = date.today()
    current_month_date = today.replace(day=1)

    previously_certified_subq = (
        db.session.query(CompanyCertification.company_id)
        .filter(
            CompanyCertification.certification_level_int > 0,
            CompanyCertification.expiration_date >= today,
            CompanyCertification.attribution_date < current_month_date,
        )
        .subquery()
    )

    nb_companies_lost_certification = (
        db.session.query(
            func.count(func.distinct(previously_certified_subq.c.company_id))
        )
        .outerjoin(
            CompanyCertification,
            (
                CompanyCertification.company_id
                == previously_certified_subq.c.company_id
            )
            & (CompanyCertification.attribution_date == current_month_date)
            & (CompanyCertification.certification_level_int > 0),
        )
        .filter(CompanyCertification.id == None)
        .scalar()
    )

    if nb_companies_lost_certification is None:
        nb_companies_lost_certification = 0

    send_mattermost_message(
        thread_title="Calcul des certificats",
        main_title="Calcul des certificats",
        main_value="Le calcul des certificats s'est bien terminé :v:",
        items=[
            {
                "title": "Nombre total d'entreprises certifiées",
                "value": nb_certified_companies,
                "short": True,
            },
            {
                "title": "Nombre d'entreprises certifiées bronze",
                "value": nb_bronze_companies,
                "short": True,
            },
            {
                "title": "Nombre d'entreprises certifiées argent",
                "value": nb_silver_companies,
                "short": True,
            },
            {
                "title": "Nombre d'entreprises certifiées or",
                "value": nb_gold_companies,
                "short": True,
            },
            {
                "title": "Nombre d'entreprises certifiées diamant",
                "value": nb_diamond_companies,
                "short": True,
            },
            {
                "title": "Nombre d'entreprises ayant perdu le certificat",
                "value": nb_companies_lost_certification,
                "short": True,
            },
            {
                "title": "Tableau metabase des entreprises ayant perdu le certificat",
                "value": "https://metabase.mobilic.beta.gouv.fr/question/257-nombre-dentreprises-certifiees-actives-et-non-actives",
                "short": True,
            },
        ],
    )
