import base64

from celery import Celery

from app import app, mailer, Company
from app.domain.permissions import ConsultationScope
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.xls.companies import (
    get_one_excel_file,
    get_archive_excel_file,
)
from app.models import User

celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)

DEFAULT_FILE_NAME = "rapport_activités"


@celery.task()
def async_export_excel(
    admin_id,
    user_ids,
    company_ids,
    min_date,
    max_date,
    one_file_by_employee,
    idx_bucket=1,
    nb_buckets=1,
    file_name=DEFAULT_FILE_NAME,
):
    with app.app_context():
        admin = User.query.get(admin_id)
        users = User.query.filter(User.id.in_(user_ids)).all()
        scope = ConsultationScope(company_ids=company_ids)
        if one_file_by_employee:
            user_wdays_batches = []
            for user in users:
                user_wdays_batches += [
                    (
                        user,
                        group_user_events_by_day_with_limit(
                            user,
                            consultation_scope=scope,
                            from_date=min_date,
                            until_date=max_date,
                            include_dismissed_or_empty_days=True,
                        )[0],
                    )
                ]
        else:
            all_users_work_days = []
            for user in users:
                all_users_work_days += group_user_events_by_day_with_limit(
                    user,
                    consultation_scope=scope,
                    from_date=min_date,
                    until_date=max_date,
                    include_dismissed_or_empty_days=True,
                )[0]
            user_wdays_batches = [(None, all_users_work_days)]

        companies = Company.query.filter(Company.id.in_(company_ids)).all()

        file_obj = {}
        if len(user_wdays_batches) == 1:
            file = get_one_excel_file(
                user_wdays_batches[0][1], companies, min_date, max_date
            )
            file_obj[
                "ContentType"
            ] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            file_obj["Filename"] = f"{file_name}.xlsx"
        else:
            file = get_archive_excel_file(
                batches=user_wdays_batches,
                companies=companies,
                min_date=min_date,
                max_date=max_date,
            )
            file_obj["ContentType"] = "application/zip"
            file_obj["Filename"] = f"{file_name}.zip"

        file_content = file.read()
        base64_content = base64.b64encode(file_content).decode("utf-8")
        file_obj["Base64Content"] = base64_content

        try:
            mailer.send_admin_export_excel(
                admin=admin,
                company_name=companies[0].usual_name,
                file=file_obj,
                subject_suffix=f" ({idx_bucket}/{nb_buckets})"
                if nb_buckets > 1
                else "",
            )
        except Exception as e:
            app.logger.exception(e)
