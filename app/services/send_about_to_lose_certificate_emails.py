from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy import exists, and_
from sqlalchemy.orm import aliased

from app import app, mailer
from app.models.company import Company
from app.models import CompanyCertification


def send_about_to_lose_certificate_emails(today):
    min_attribution_date = today.replace(day=1) - relativedelta(months=3)

    companies_about_to_lose_certificate = (
        companies_about_to_lose_certification(min_attribution_date)
    )
    for company in companies_about_to_lose_certificate:
        current_admins = company.get_admins(date.today(), None)
        for admin in current_admins:
            try:
                app.logger.info(
                    f"Sending company about to lose certificate email to user {admin.id} for company {company.id}."
                )
                mailer.send_admin_about_to_lose_certificate_email(
                    company, admin, min_attribution_date
                )
            except Exception as e:
                app.logger.exception(e)
    return


def companies_about_to_lose_certification(min_attribution_date):
    max_attribution_date = min_attribution_date + relativedelta(months=1)
    company_certification_1 = aliased(CompanyCertification)
    company_certification_2 = aliased(CompanyCertification)

    return (
        Company.query.join(
            company_certification_1,
            company_certification_1.company_id == Company.id,
        )
        .filter(
            company_certification_1.attribution_date >= min_attribution_date,
            company_certification_1.be_active,
            company_certification_1.be_compliant,
            company_certification_1.not_too_many_changes,
            company_certification_1.validate_regularly,
            company_certification_1.log_in_real_time,
            ~exists().where(
                and_(
                    company_certification_1.company_id
                    == company_certification_2.company_id,
                    company_certification_2.attribution_date
                    >= max_attribution_date,
                    company_certification_2.be_active,
                    company_certification_2.be_compliant,
                    company_certification_2.not_too_many_changes,
                    company_certification_2.validate_regularly,
                    company_certification_2.log_in_real_time,
                )
            ),
        )
        .distinct()
        .all()
    )
