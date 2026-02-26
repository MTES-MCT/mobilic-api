from app import app
from app.helpers.xls.signature import retrieve_and_verify_signature

from .companies import get_one_excel_file, get_archive_excel_file
from app.models import User, Company
from app.domain.permissions import ConsultationScope
from app.domain.work_days import group_user_events_by_day_with_limit


def generate_admin_export_file(
    user_ids, company_ids, one_file_by_employee, min_date, max_date, file_name
):
    app.logger.info(
        f"Generating export user_ids={user_ids} company_ids={company_ids} min_date={min_date} max_date={max_date} one_file_by_employee={one_file_by_employee}"
    )
    users = User.query.filter(User.id.in_(user_ids)).all()
    scope = ConsultationScope(company_ids=company_ids)
    if one_file_by_employee:
        user_wdays_batches = []
        for user in users:
            user_timezone = user.timezone
            user_wdays_batches += [
                (
                    user,
                    group_user_events_by_day_with_limit(
                        user,
                        consultation_scope=scope,
                        from_date=min_date,
                        until_date=max_date,
                        include_dismissed_or_empty_days=True,
                        tz=user_timezone
                    )[0],
                )
            ]
    else:
        all_users_work_days = []
        for user in users:
            user_timezone = user.timezone
            all_users_work_days += group_user_events_by_day_with_limit(
                user,
                consultation_scope=scope,
                from_date=min_date,
                until_date=max_date,
                include_dismissed_or_empty_days=True,
                tz=user_timezone
            )[0]
        user_wdays_batches = [(None, all_users_work_days)]

    companies = Company.query.filter(Company.id.in_(company_ids)).all()

    if len(user_wdays_batches) == 1:
        file = get_one_excel_file(
            user_wdays_batches[0][1], companies, min_date, max_date
        )
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        ext = "xlsx"
    else:
        file = get_archive_excel_file(
            batches=user_wdays_batches,
            companies=companies,
            min_date=min_date,
            max_date=max_date,
        )
        content_type = "application/zip"
        ext = "zip"

    file_name = f"{file_name}.{ext}"
    file.seek(0)
    file_content = file.read()
    file_size_bytes = len(file_content)
    file.seek(0)

    return file_content, content_type, file_name, file_size_bytes
