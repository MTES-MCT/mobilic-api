from datetime import date

from app import app, mailer
from app.domain.company import (
    find_active_company_ids_in_period,
    find_companies_by_ids,
)
from app.helpers.time import previous_month_period


def send_active_then_inactive_companies_emails(today):
    last_month_start, last_month_end = previous_month_period(today)
    two_months_ago_start, two_months_ago_end = previous_month_period(
        last_month_start
    )

    company_ids_active_two_months_ago = find_active_company_ids_in_period(
        start_period=two_months_ago_start,
        end_period=two_months_ago_end,
    )
    app.logger.info(
        f"{len(company_ids_active_two_months_ago)} companies were active two months ago ({two_months_ago_start} {two_months_ago_end})"
    )

    company_ids_active_last_month = find_active_company_ids_in_period(
        start_period=last_month_start, end_period=last_month_end
    )

    companies = find_companies_by_ids(
        [
            company_id
            for company_id in company_ids_active_two_months_ago
            if company_id not in company_ids_active_last_month
        ]
    )

    app.logger.info(
        f"{len(companies)} companies were then not active last month ({last_month_start} {last_month_end})"
    )

    admins = []
    for company in companies:
        admins += company.get_admins(date.today(), None)
    admins = list(set(admins))

    app.logger.info(f"Will send an email to {len(admins)} admins")
    for admin in admins:
        try:
            app.logger.info(
                f"Sending company not active anymore email to admin {admin.id}"
            )
            mailer.send_active_then_inactive_companies_email(admin)
        except Exception as e:
            app.logger.exception(e)
