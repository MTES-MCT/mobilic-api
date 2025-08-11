from datetime import date

from dateutil.relativedelta import relativedelta

from app import app, mailer
from app.domain.company import get_start_last_certification_period
from app.domain.email import check_email_exists
from app.helpers.mail_type import EmailType
from app.jobs import log_execution
from app.models import CompanyCertification
from app.models.company import Company
from app.models.company_certification import (
    CERTIFICATION_REAL_TIME_BRONZE,
    CERTIFICATION_ADMIN_CHANGES_BRONZE,
)

NB_MONTHS_AGO = 1


@log_execution
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
        current_certification = CompanyCertification.query.filter(
            CompanyCertification.company_id == company.id,
            CompanyCertification.attribution_date
            == current_month_attribution_date,
        ).one_or_none()

        display_real_time_criteria = True
        display_admin_changes_criteria = True
        if current_certification:
            display_real_time_criteria = (
                current_certification.log_in_real_time
                < CERTIFICATION_REAL_TIME_BRONZE
            )
            display_admin_changes_criteria = (
                current_certification.admin_changes
                > CERTIFICATION_ADMIN_CHANGES_BRONZE
            )

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
                    company,
                    admin,
                    attribution_date,
                    display_real_time_criteria,
                    display_admin_changes_criteria,
                )
            except Exception as e:
                app.logger.exception(e)


def companies_about_to_lose_certification(
    max_attribution_date, current_month_attribution_date, today
):

    company_ids_certified_today = [
        company_id
        for company_id, in CompanyCertification.query.filter(
            CompanyCertification.admin_changes
            <= CERTIFICATION_ADMIN_CHANGES_BRONZE,
            CompanyCertification.log_in_real_time
            >= CERTIFICATION_REAL_TIME_BRONZE,
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
            CompanyCertification.admin_changes
            <= CERTIFICATION_ADMIN_CHANGES_BRONZE,
            CompanyCertification.log_in_real_time
            >= CERTIFICATION_REAL_TIME_BRONZE,
            CompanyCertification.expiration_date > today,
            ~Company.id.in_(company_ids_certified_today),
        )
        .distinct()
        .all()
    )

    return companies_certified_before_min_attribution_date
