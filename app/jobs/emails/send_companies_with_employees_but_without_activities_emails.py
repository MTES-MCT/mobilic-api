from datetime import timedelta

from app import app, mailer
from app.domain.company import (
    find_admins_of_companies_with_an_employee_but_without_any_activity,
)
from app.jobs import log_execution

NB_DAYS_AGO = 10


@log_execution
def send_companies_with_employees_but_without_activities_emails(today):

    trigger_date = today - timedelta(days=NB_DAYS_AGO)
    admin_employments = (
        find_admins_of_companies_with_an_employee_but_without_any_activity(
            first_employee_invitation_date=trigger_date
        )
    )

    app.logger.info(
        f"{len(admin_employments)} mails to send for companies with employee but without any activity"
    )
    for admin_employment in admin_employments:
        try:
            app.logger.info(
                f"Sending company with employee but without any activity email to admin #{admin_employment.user.id}"
            )
            mailer.send_companies_with_employees_but_with_no_activity(
                employment=admin_employment
            )
        except Exception as e:
            app.logger.exception(e)
