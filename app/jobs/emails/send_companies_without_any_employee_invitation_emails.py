from datetime import timedelta

from app import app, mailer
from app.domain.company import (
    find_admins_of_companies_without_any_employee_invitations,
)
from app.jobs import log_execution

NB_DAYS_AGO = 14


@log_execution
def send_companies_without_any_employee_invitation_emails(today):

    trigger_date = today - timedelta(days=NB_DAYS_AGO)
    admin_employments = (
        find_admins_of_companies_without_any_employee_invitations(
            company_creation_trigger_date=trigger_date,
            companies_to_exclude=app.config[
                "COMPANY_EXCLUDE_ONBOARDING_EMAILS"
            ],
        )
    )

    app.logger.info(
        f"{len(admin_employments)} mails to send for companies without any invitations"
    )
    for admin_employment in admin_employments:
        try:
            app.logger.info(
                f"Sending company without any invitation email to admin #{admin_employment.user.id}"
            )
            mailer.send_companies_without_invitations_email(
                employment=admin_employment
            )
        except Exception as e:
            app.logger.exception(e)
