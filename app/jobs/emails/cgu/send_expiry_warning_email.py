from datetime import datetime, timedelta

from app import app, db, mailer
from app.helpers.mail import MailjetError
from app.jobs import log_execution
from app.models import UserAgreement, User

DELAY_HOURS = 72


@log_execution
def send_expiry_warning_email():
    users, expiry_date = get_users_expiring_soon()

    for user in users:
        try:
            is_admin = user.is_an_admin
            mailer.send_cgu_expiry_warning_email(
                user=user,
                expiry_date=expiry_date,
                is_admin=is_admin,
            )
        except MailjetError as e:
            app.logger.exception(e)


def get_users_expiring_soon():
    cgu_version = app.config["CGU_VERSION"]

    trigger_datetime_max = datetime.now() + timedelta(hours=DELAY_HOURS)
    trigger_datetime_min = trigger_datetime_max - timedelta(hours=24)

    # find users expiring in 3 days
    users = (
        db.session.query(User)
        .join(UserAgreement)
        .filter(
            UserAgreement.cgu_version == cgu_version,
            UserAgreement.expires_at < trigger_datetime_max,
            UserAgreement.expires_at >= trigger_datetime_min,
        )
        .all()
    )

    return users, trigger_datetime_max.date()
