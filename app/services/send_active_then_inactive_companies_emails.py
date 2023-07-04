from app import app, mailer
from app.domain.company import (
    find_active_companies_in_period,
    get_admin_of_companies,
)
from app.helpers.time import previous_month_period


def send_active_then_inactive_companies_emails(today):
    last_month_start, last_month_end = previous_month_period(today)
    two_months_ago_start, two_months_ago_end = previous_month_period(
        last_month_start
    )

    companies_active_two_months_ago = find_active_companies_in_period(
        start_period=two_months_ago_start.date(),
        end_period=two_months_ago_end.date(),
    )
    app.logger.info(
        f"{len(companies_active_two_months_ago)} companies where active two months ago ({two_months_ago_start.date()} {two_months_ago_end.date()})"
    )

    companies_active_last_month = find_active_companies_in_period(
        start_period=last_month_start.date(), end_period=last_month_end.date()
    )

    companies = [
        company
        for company in companies_active_two_months_ago
        if company not in companies_active_last_month
    ]
    app.logger.info(
        f"{len(companies)} companies where then not active last month ({last_month_start.date()} {last_month_end.date()})"
    )

    admins = get_admin_of_companies(
        company_ids=[company[0] for company in companies]
    )
    app.logger.info(f"Will send an email to {len(admins)} admins")
    for admin_id, _, admin_last_name in admins:
        try:
            app.logger.info(
                f"Sending company not active anymore email to admin {admin_id}"
            )
            mailer.send_active_then_inactive_companies_email(admin_last_name)
        except Exception as e:
            app.logger.exception(e)
