from datetime import datetime, timedelta

from sqlalchemy import func, exists, and_

from app import mailer, app
from app.helpers.mail_type import EmailType
from app.models import Employment, Email
from app.models.employment import EmploymentRequestValidationStatus


def send_onboarding_emails(today):
    signup_date = today - timedelta(days=7)

    recent_user_signups = Employment.query.filter(
        func.date_trunc("day", Employment.validation_time)
        == datetime(
            signup_date.year,
            signup_date.month,
            signup_date.day,
        ),
        ~Employment.has_admin_rights,
        Employment.validation_status
        == EmploymentRequestValidationStatus.APPROVED,
        ~Employment.is_dismissed,
        ~exists().where(
            and_(
                Email.user_id == Employment.user_id,
                Email.type == EmailType.WORKER_ONBOARDING_SECOND_INFO,
            )
        ),
    ).all()

    # Keep track of users we send emails to in order to avoid writing to a user twice in the same batch
    processed_users = set()

    for employment in recent_user_signups:
        user = employment.user

        if user in processed_users:
            continue

        try:
            app.logger.info(
                f"Sending second email of worker onboarding to {user}"
            )
            mailer.send_worker_onboarding_second_email(user)
            processed_users.add(user)
        except Exception as e:
            app.logger.exception(e)
        continue
