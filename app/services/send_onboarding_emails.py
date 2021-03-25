from datetime import date, datetime, timedelta
from sqlalchemy.orm import selectinload

from app.models import User, Employment
from app.helpers.mail_type import EmailType
from app import mailer, app


def send_onboarding_emails(today):
    oldest_signup_date = today - timedelta(days=4)

    recent_user_or_company_signups = (
        Employment.query.options(
            selectinload(Employment.user).joinedload(User.emails),
            selectinload(Employment.company),
        )
        .filter(
            Employment.validation_time
            >= datetime(
                oldest_signup_date.year,
                oldest_signup_date.month,
                oldest_signup_date.day,
            )
        )
        .all()
    )

    # Keep track of users we send emails to in order to avoid writing to a user twice in the same batch
    target_users = set()

    for employment in sorted(
        recent_user_or_company_signups,
        key=lambda e: 0 if e.has_admin_rights else 1,
    ):
        user = employment.user
        company = employment.company
        company_creation_time = company.creation_time.date()

        if user in target_users:
            continue

        # Send manager onboarding emails
        if employment.has_admin_rights:
            if company_creation_time == today - timedelta(days=1):
                if all(
                    [
                        e.type != EmailType.MANAGER_ONBOARDING_FIRST_INFO
                        for e in user.emails
                    ]
                ):
                    target_users.add(user)
                    try:
                        app.logger.info(
                            f"Sending first email of manager onboarding to {user}"
                        )
                        mailer.send_manager_onboarding_first_email(
                            user, company
                        )
                    except Exception as e:
                        app.logger.exception(e)
                    continue

            elif company_creation_time == today - timedelta(days=4):
                if all(
                    [
                        e.type != EmailType.MANAGER_ONBOARDING_SECOND_INFO
                        for e in user.emails
                    ]
                ):
                    target_users.add(user)
                    try:
                        app.logger.info(
                            f"Sending second email of manager onboarding to {user}"
                        )
                        mailer.send_manager_onboarding_second_email(user)
                    except Exception as e:
                        app.logger.exception(e)
                    continue

        else:
            if employment.validation_time.date() == today - timedelta(days=1):
                if all(
                    [
                        e.type != EmailType.WORKER_ONBOARDING_FIRST_INFO
                        for e in user.emails
                    ]
                ):
                    target_users.add(user)
                    try:
                        app.logger.info(
                            f"Sending first email of worker onboarding to {user}"
                        )
                        mailer.send_worker_onboarding_first_email(user)
                    except Exception as e:
                        app.logger.exception(e)
                    continue

            elif employment.validation_time.date() == today - timedelta(
                days=2
            ):
                if all(
                    [
                        e.type != EmailType.WORKER_ONBOARDING_SECOND_INFO
                        for e in user.emails
                    ]
                ):
                    target_users.add(user)
                    try:
                        app.logger.info(
                            f"Sending second email of worker onboarding to {user}"
                        )
                        mailer.send_worker_onboarding_second_email(user)
                    except Exception as e:
                        app.logger.exception(e)
                    continue


if __name__ == "__main__":
    send_onboarding_emails(date.today())
