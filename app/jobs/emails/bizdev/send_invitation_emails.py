from app import app, db, mailer
from datetime import timedelta

from app.controllers.utils import atomic_transaction
from app.helpers.mail import MailjetError
from app.domain.company import find_employee_for_invitation
from app.jobs import log_execution

NB_DAYS_AGO = 7
START_DATE = app.config["START_DATE_FOR_SCHEDULED_INVITATION"]
MAILJET_BATCH_SEND_LIMIT = 50


@log_execution
def send_invitation_emails(today):
    app.logger.info("Starting the invitation email sending process.")

    trigger_date = today - timedelta(days=NB_DAYS_AGO)
    max_start_date = START_DATE

    if max_start_date:
        app.logger.info(
            f"Emails will only be sent for employments created between {max_start_date} and {trigger_date}."
        )
    else:
        app.logger.info(
            f"Emails will be sent for employments until {trigger_date}."
        )

    employments = find_employee_for_invitation(
        trigger_date, max_start_date=max_start_date
    )
    app.logger.info(
        f"Found {len(employments)} employments for sending invitations."
    )

    if employments:
        with atomic_transaction(commit_at_end=True):
            messages = []
            for cursor in range(0, len(employments), MAILJET_BATCH_SEND_LIMIT):
                batch = employments[cursor : cursor + MAILJET_BATCH_SEND_LIMIT]
                app.logger.info(
                    f"Sending batch {cursor // MAILJET_BATCH_SEND_LIMIT + 1} with {len(batch)} employments."
                )
                messages.extend(
                    mailer.batch_send_employee_invites(
                        batch,
                        reminder=False,
                        disable_commit=True,
                        scheduled_reminder=True,
                    )
                )

            unsent_employments = []
            for index, message in enumerate(messages):
                if isinstance(message.response, MailjetError):
                    unsent_employments.append(employments[index])
                    db.session.delete(employments[index])
                    app.logger.error(
                        f"Error sending email to {employments[index].email}: {message.response}"
                    )

            app.logger.info(
                f"Emails sent for {len(employments) - len(unsent_employments)} employments. "
                f"{len(unsent_employments)} employments failed."
            )

    app.logger.info("Finished the invitation email sending process.")
