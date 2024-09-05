from datetime import timedelta

from app import mailer, app
from app.domain.company import get_admin_of_companies_without_activity
from app.jobs import log_execution


@log_execution
def send_never_active_companies_emails(today):
    min_inactivity_period = today - timedelta(days=6)
    old_companies_signup_threshold = today - timedelta(days=14)

    old_inactive_companies_admin = get_admin_of_companies_without_activity(
        max_signup_date=old_companies_signup_threshold,
        companies_to_exclude=app.config["COMPANY_EXCLUDE_ONBOARDING_EMAILS"],
    )
    recent_inactive_companies_admin = get_admin_of_companies_without_activity(
        max_signup_date=min_inactivity_period,
        min_signup_date=old_companies_signup_threshold,
        companies_to_exclude=app.config["COMPANY_EXCLUDE_ONBOARDING_EMAILS"],
    )

    app.logger.info(
        f"{len(old_inactive_companies_admin)} mails to send for never active old companies"
    )
    app.logger.info(
        f"{len(recent_inactive_companies_admin)} mails to send for recent active old companies"
    )
    for employment in old_inactive_companies_admin:
        try:
            app.logger.info(
                f"Sending never active old company email for employment {employment.id}"
            )
            mailer.send_old_never_active_companies_email(employment)
        except Exception as e:
            app.logger.exception(e)
    for employment in recent_inactive_companies_admin:
        try:
            app.logger.info(
                f"Sending never active recent company email for employment {employment.id}"
            )
            mailer.send_recent_never_active_companies_email(
                employment=employment,
                company_name=employment.company.usual_name,
                signup_date=employment.company.creation_time.strftime(
                    "%d/%m/%Y"
                ),
            )
        except Exception as e:
            app.logger.exception(e)
