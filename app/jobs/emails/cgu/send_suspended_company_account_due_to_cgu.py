from app import app, db, mailer
from app.helpers.mail import MailjetError
from app.models import UserAgreement, Employment, Company, User
from app.models.employment import EmploymentRequestValidationStatus
from app.models.user_agreement import UserAgreementStatus


def send_suspended_company_account_due_to_cgu(now):

    cgu_version = app.config["CGU_VERSION"]

    # Find user agreements expiring today
    newly_expired_user_agreements = UserAgreement.query.filter(
        UserAgreement.cgu_version == cgu_version,
        UserAgreement.status == UserAgreementStatus.REJECTED,
        UserAgreement.is_blacklisted.is_(False),
        UserAgreement.expires_at < now,
    ).all()

    user_ids = [ua.user_id for ua in newly_expired_user_agreements]

    # Find which users are company admins
    admin_employments = Employment.query.filter(
        Employment.user_id.in_(user_ids),
        Employment.has_admin_rights,
        ~Employment.is_dismissed,
        Employment.end_date.is_(None),
        Employment.validation_status
        == EmploymentRequestValidationStatus.APPROVED,
    ).all()

    company_ids = [employment.company_id for employment in admin_employments]
    companies = Company.query.filter(Company.id.in_(company_ids)).all()

    # Updating is_blacklisted flag for newly expired user agreements
    for ua in newly_expired_user_agreements:
        ua.is_blacklisted = True
    db.session.commit()

    # For each company, find which ones do not have any non-blacklisted admin after today
    today = now.date()
    admin_ids = []
    for company in companies:
        company_admins = company.get_admins(start=today, end=today)
        blacklisted_admins = UserAgreement.query.filter(
            UserAgreement.user_id.in_([admin.id for admin in company_admins]),
            UserAgreement.is_blacklisted,
        ).all()

        if len(company_admins) > len(blacklisted_admins):
            continue

        admin_ids += [a.id for a in company_admins]

    # Send email to every admin of these companies
    admin_ids = list(set(admin_ids))
    admins = User.query.filter(User.id.in_(admin_ids)).all()

    try:
        mailer.send_admins_company_suspended_cgu_email(admins=admins)
    except MailjetError as e:
        app.logger.exception(e)
