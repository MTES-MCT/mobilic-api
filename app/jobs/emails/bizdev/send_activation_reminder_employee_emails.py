from datetime import timedelta, date

from app import app, mailer
from app.domain.user import (
    find_employees_for_activation_reminder_d2,
    find_employees_for_activation_reminder_d4,
)
from app.jobs import log_execution

NB_DAYS_D2 = 2
NB_DAYS_D4 = 4


@log_execution
def send_activation_reminder_employee_emails(today=None):
    if today is None:
        today = date.today()

    trigger_date_d2 = today - timedelta(days=NB_DAYS_D2)
    users_d2 = find_employees_for_activation_reminder_d2(trigger_date_d2)
    app.logger.info(
        f"-- will send {len(users_d2)} employee activation reminder"
        f" D+2 emails"
    )
    for user in users_d2:
        try:
            app.logger.info(f"-- sending D+2 activation reminder to {user}")
            mailer.send_activation_reminder_employee_d2(user)
        except Exception as e:
            app.logger.exception(e)

    trigger_date_d4 = today - timedelta(days=NB_DAYS_D4)
    users_d4 = find_employees_for_activation_reminder_d4(trigger_date_d4)
    app.logger.info(
        f"-- will send {len(users_d4)} employee activation reminder"
        f" D+4 emails"
    )
    for user in users_d4:
        try:
            app.logger.info(f"-- sending D+4 activation reminder to {user}")
            mailer.send_activation_reminder_employee_d4(user)
        except Exception as e:
            app.logger.exception(e)
