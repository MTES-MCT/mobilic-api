from sqlalchemy.sql.functions import now

from app import db
from app.helpers.mattermost import send_mattermost_message
from app.models import CompanyCertification


def send_certificate_compute_end_notification():
    nb_certified_companies = (
        db.session.query(CompanyCertification.company_id)
        .filter(
            CompanyCertification.be_active,
            CompanyCertification.be_compliant,
            CompanyCertification.not_too_many_changes,
            CompanyCertification.validate_regularly,
            CompanyCertification.log_in_real_time,
            CompanyCertification.expiration_date > now(),
        )
        .distinct()
        .count()
    )

    send_mattermost_message(
        thread_title="Calcul des certificats",
        main_title="Calcul des certificats",
        main_value="Le calcul des certificats s'est bien terminé :v:",
        items=[
            {
                "title": "Nombre d'entreprises certifiées",
                "value": nb_certified_companies,
                "short": True,
            },
            {
                "title": "Tableau metabase de suivi des certifications",
                "value": "https://metabase.mobilic.beta.gouv.fr/question/257-nombre-dentreprises-certifiees-actives-et-non-actives",
                "short": True,
            },
        ],
    )
