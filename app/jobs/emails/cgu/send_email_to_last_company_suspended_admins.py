from app import app, db, mailer
from app.helpers.mail import MailjetError
from app.jobs import log_execution
from app.models import UserAgreement, Company, User
from app.models.user_agreement import UserAgreementStatus


@log_execution
def send_email_to_last_company_suspended_admins(now):
    cgu_version = app.config["CGU_VERSION"]

    users_expiring_today = (
        db.session.query(User)
        .join(UserAgreement)
        .filter(
            UserAgreement.cgu_version == cgu_version,
            UserAgreement.status == UserAgreementStatus.REJECTED,
            UserAgreement.is_blacklisted.is_(False),
            UserAgreement.expires_at < now,
        )
        .all()
    )
    today = now.date()
    for user in users_expiring_today:
        admin_company_ids = user.current_company_ids_with_admin_rights

        UserAgreement.blacklist_user(user.id)

        # user is not an admin
        if len(admin_company_ids) == 0:
            continue

        admin_companies = Company.query.filter(
            Company.id.in_(admin_company_ids)
        ).all()
        for company in admin_companies:
            admins = company.get_admins(start=today, end=today)

            # company still has at least one admin, skip email
            if len(admins) > 0:
                continue

            try:
                mailer.send_admin_company_suspended_cgu_email(admin=user)
            except MailjetError as e:
                app.logger.exception(e)
