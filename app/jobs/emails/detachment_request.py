from app import app, mailer
from app.helpers.celery import celery
from app.helpers.mail import InvalidEmailAddressError
from app.models import User
from app.models.employment import Employment


@celery.task(autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_detachment_request_email(employment_id, admin_id, request_date=None):
    """Send the detachment request (or relance, when request_date is set)
    to a single admin. One task per admin so that a retry never re-sends
    the email to admins who already received it."""
    with app.app_context():
        employment = Employment.query.get(employment_id)
        admin = User.query.get(admin_id)
        if not employment or not admin:
            return

        try:
            if request_date:
                mailer.send_detachment_relance_email(
                    employment, admin, request_date
                )
            else:
                mailer.send_detachment_request_email(employment, admin)
        except InvalidEmailAddressError as e:
            # Retrying won't fix an invalid address
            app.logger.warning(e)
