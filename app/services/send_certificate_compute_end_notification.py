import requests
from sqlalchemy.sql.functions import now

from app import app, db
from app.models import CompanyCertification
from config import MOBILIC_ENV


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
    requests.post(
        app.config["MATTERMOST_WEBHOOK"],
        json=dict(
            channel=app.config["MATTERMOST_MAIN_CHANNEL"],
            username=f"Calcul des certificats - {MOBILIC_ENV.capitalize()}",
            icon_emoji=":robot:",
            attachments=[
                dict(
                    title="Calcul des certificats",
                    text="Le calcul des certificats s'est bien terminé :v:",
                    fields=[
                        {
                            "title": "Nombre d'entreprises certifiées",
                            "value": nb_certified_companies,
                            "short": True,
                        },
                        {
                            "title": "Tableau metabase de suivi des certifications",
                            "value": "https://metabase.mobilic.beta.gouv.fr/dashboard/21-evolution-entreprises-certifiees",
                            "short": True,
                        },
                    ],
                )
            ],
        ),
    )
