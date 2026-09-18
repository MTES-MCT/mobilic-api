from app import app, mailer
from app.helpers.celery import celery
from app.helpers.oauth.models import (
    OAuth2Client,
    ThirdPartyClientEmployment,
)
from app.models.employment import Employment

EMAIL_GENERATORS = {
    "account_creation": "generate_third_party_software_account_creation_email",
    "employment_creation": (
        "generate_third_party_software_employment_creation_email"
    ),
    "employment_access": (
        "generate_third_party_software_employment_access_email"
    ),
}


@celery.task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_third_party_sync_emails(client_id, entries):
    with app.app_context():
        client = OAuth2Client.query.get(client_id)
        if not client:
            return

        messages = []
        for entry in entries:
            employment = Employment.query.get(entry["employment_id"])
            if not employment:
                continue
            link = ThirdPartyClientEmployment.query.filter(
                ThirdPartyClientEmployment.employment_id == employment.id,
                ThirdPartyClientEmployment.client_id == client_id,
                ~ThirdPartyClientEmployment.is_dismissed,
            ).first()
            generate = getattr(mailer, EMAIL_GENERATORS[entry["kind"]])
            messages.append(
                generate(link, employment, client, employment.user)
            )

        if messages:
            mailer.send_batch(messages)
