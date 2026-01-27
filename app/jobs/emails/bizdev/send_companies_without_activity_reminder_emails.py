from datetime import timedelta

from app import app, mailer
from app.domain.company import (
    find_admins_of_companies_still_without_activity_for_reminder,
)
from app.jobs import log_execution

NB_DAYS_AFTER_FIRST_EMAIL = 7


@log_execution
def send_companies_without_activity_reminder_emails(today):

    trigger_date = today - timedelta(days=NB_DAYS_AFTER_FIRST_EMAIL)
    admin_employments = (
        find_admins_of_companies_still_without_activity_for_reminder(
            received_first_email_before_date=trigger_date,
            companies_to_exclude=app.config[
                "COMPANY_EXCLUDE_ONBOARDING_EMAILS"
            ],
        )
    )

    app.logger.info(f"-- will send {len(admin_employments)} reminder emails")
    for admin_employment in admin_employments:
        try:
            app.logger.info(f"-- sending reminder email to {admin_employment}")
            mailer.send_companies_with_employees_but_with_no_activity_reminder(
                employment=admin_employment
            )
        except Exception as e:
            app.logger.exception(e)
