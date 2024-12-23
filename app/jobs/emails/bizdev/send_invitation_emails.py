from datetime import timedelta

from app import app, mailer
from app.domain.company import find_employee_for_invitation
from app.jobs import log_execution

NB_DAYS_AGO = 7


@log_execution
def send_invitation_emails(today):
    app.logger.info("Starting the invitation email sending process.")

    trigger_date = today - timedelta(days=NB_DAYS_AGO)

    employments = find_employee_for_invitation(trigger_date)
    app.logger.info(
        f"Found {len(employments)} employments for sending invitations."
    )

    if employments:
        try:
            mailer.batch_send_employee_invites(
                employments,
                reminder=False,
                disable_commit=False,
                scheduled_reminder=True,
            )
            app.logger.info(f"Emails sent for {len(employments)} employments.")
        except Exception as e:
            app.logger.error("Error during batch email sending.")
            app.logger.exception(e)

    app.logger.info("Finished the invitation email sending process.")
