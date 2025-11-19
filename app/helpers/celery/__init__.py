import base64

from celery import Celery

from app import app, Company, db
from app.domain.permissions import ConsultationScope
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.s3 import S3Client
from app.helpers.xls.companies import (
    get_one_excel_file,
    get_archive_excel_file,
)
from app.models import User, Export
from app.models.export import ExportStatus, ExportType

celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)

DEFAULT_FILE_NAME = "rapport_activités"


@celery.task()
def async_export_excel(
    exporter_id,
    user_ids,
    company_ids,
    min_date,
    max_date,
    one_file_by_employee,
    file_name=DEFAULT_FILE_NAME,
    export_type=ExportType.EXCEL,
):
    with app.app_context():
        exporter = User.query.get(exporter_id)

        export = Export(
            user=exporter,
            export_type=export_type,
            context={
                "exporter_id": exporter_id,
                "user_ids": user_ids,
                "company_ids": company_ids,
                "min_date": min_date.isoformat(),
                "max_date": max_date.isoformat(),
                "one_file_by_employee": one_file_by_employee,
            },
        )
        db.session.add(export)
        db.session.commit()

        try:
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

            if len(user_wdays_batches) == 1:
                file = get_one_excel_file(
                    user_wdays_batches[0][1], companies, min_date, max_date
                )
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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

            file_content = file.read()
            base64_content = base64.b64encode(file_content).decode("utf-8")

            path = f"exports/{exporter_id}/{export.id}"
            S3Client.upload_export(base64_content, path, content_type)

            export.status = ExportStatus.READY
            export.file_s3_path = path
            export.file_type = content_type
            export.file_name = file_name
            db.session.commit()

        except Exception as e:

            export.status = ExportStatus.FAILED
            db.session.commit()
            raise e
