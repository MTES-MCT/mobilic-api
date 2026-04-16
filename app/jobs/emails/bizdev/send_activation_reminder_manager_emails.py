from datetime import timedelta, date

from app import app, mailer
from app.domain.user import find_managers_for_activation_reminder_d2
from app.jobs import log_execution

NB_DAYS_D2 = 2


@log_execution
def send_activation_reminder_manager_emails(today=None):
    if today is None:
        today = date.today()

    trigger_date_d2 = today - timedelta(days=NB_DAYS_D2)
    users_d2 = find_managers_for_activation_reminder_d2(trigger_date_d2)
    app.logger.info(
        f"-- will send {len(users_d2)} manager activation reminder"
        f" D+2 emails"
    )
    for user in users_d2:
        try:
            app.logger.info(
                f"-- sending D+2 activation reminder to manager {user}"
            )
            mailer.send_activation_reminder_manager_d2(user)
        except Exception as e:
            app.logger.exception(e)
