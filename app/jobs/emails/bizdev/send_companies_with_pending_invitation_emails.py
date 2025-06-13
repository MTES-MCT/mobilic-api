from datetime import timedelta, date

from app import app, mailer
from app.domain.company import find_admins_with_pending_invitation
from app.jobs import log_execution

NB_DAYS_AFTER_SCHEDULED_INVITATION = 2


@log_execution
def send_companies_with_pending_invitation_emails(today=None):
    if today is None:
        today = date.today()

    pending_invitation_trigger_date = today - timedelta(
        days=NB_DAYS_AFTER_SCHEDULED_INVITATION
    )
    admins = find_admins_with_pending_invitation(
        pending_invitation_trigger_date,
        companies_to_exclude=app.config["COMPANY_EXCLUDE_ONBOARDING_EMAILS"],
    )
    app.logger.info(
        f"Found {len(admins)} admins to notify (pending invitation J+2 after scheduled invitation)."
    )

    app.logger.info(f"-- will send {len(admins)} emails")
    for admin in admins:
        try:
            app.logger.info(f"-- sending email to {admin}")
            mailer.send_companies_with_pending_invitation(employment=admin)
        except Exception as e:
            app.logger.exception(e)
