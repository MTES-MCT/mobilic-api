from datetime import timedelta

from app import app, mailer
from app.domain.company import find_admins_of_companies_without_any_invitations
from app.jobs import log_execution

NB_DAYS_AGO = 14


@log_execution
def send_companies_without_any_invitation_emails(today):

    from_date = today - timedelta(days=NB_DAYS_AGO + 1)
    to_date = today - timedelta(days=NB_DAYS_AGO)
    admin_employments = find_admins_of_companies_without_any_invitations(
        company_creation_from_date=from_date, company_creation_to_date=to_date
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
