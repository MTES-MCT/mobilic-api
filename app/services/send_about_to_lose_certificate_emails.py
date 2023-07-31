from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy.sql.functions import now

from app import app, mailer
from app.domain.company import get_start_last_certification_period
from app.domain.email import check_email_exists
from app.helpers.mail_type import EmailType
from app.models.company import Company
from app.models import CompanyCertification

NB_MONTHS_AGO = 3


def send_about_to_lose_certificate_emails(today):
    max_attribution_date = today.replace(day=1) - relativedelta(
        months=NB_MONTHS_AGO
    )
    current_month_attribution_date = today.replace(day=1)

    companies_about_to_lose_certificate = (
        companies_about_to_lose_certification(
            max_attribution_date, current_month_attribution_date, today
        )
    )
    for company in companies_about_to_lose_certificate:
        current_admins = company.get_admins(date.today(), None)
        attribution_date = get_start_last_certification_period(company.id)

        for admin in current_admins:
            # if we already sent the email since company is certified, do not send it again
            email_sent = check_email_exists(
                email_type=EmailType.COMPANY_ABOUT_TO_LOSE_CERTIFICATE,
                user_id=admin.id,
                since_date=attribution_date,
            )
            if email_sent:
                continue

            try:
                app.logger.info(
                    f"Sending company about to lose certificate email to user {admin.id} for company {company.id}. Attribution date {attribution_date}"
                )
                mailer.send_admin_about_to_lose_certificate_email(
                    company, admin, attribution_date
                )
            except Exception as e:
                app.logger.exception(e)


def companies_about_to_lose_certification(
    max_attribution_date, current_month_attribution_date, today
):

    company_ids_certified_today = [
        company_id
        for company_id, in CompanyCertification.query.filter(
            CompanyCertification.be_active,
            CompanyCertification.be_compliant,
            CompanyCertification.not_too_many_changes,
            CompanyCertification.validate_regularly,
            CompanyCertification.log_in_real_time,
            CompanyCertification.attribution_date
            == current_month_attribution_date,
        )
        .with_entities(CompanyCertification.company_id)
        .all()
    ]

    companies_certified_before_min_attribution_date = (
        Company.query.join(
            CompanyCertification, CompanyCertification.company_id == Company.id
        )
        .filter(
            CompanyCertification.attribution_date <= max_attribution_date,
            CompanyCertification.be_active,
            CompanyCertification.be_compliant,
            CompanyCertification.not_too_many_changes,
            CompanyCertification.validate_regularly,
            CompanyCertification.log_in_real_time,
            CompanyCertification.expiration_date > today,
            ~Company.id.in_(company_ids_certified_today),
        )
        .distinct()
        .all()
    )

    return companies_certified_before_min_attribution_date
