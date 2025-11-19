import time

from celery import Celery

from app import app, db
from app.helpers.s3 import S3Client
from app.helpers.xls import generate_admin_export_file
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
            start_time = time.perf_counter()
            base64_content, content_type, file_name, file_size_bytes = (
                generate_admin_export_file(
                    user_ids=user_ids,
                    company_ids=company_ids,
                    one_file_by_employee=one_file_by_employee,
                    min_date=min_date,
                    max_date=max_date,
                    file_name=file_name,
                )
            )
            end_time = time.perf_counter()
            export.file_size = file_size_bytes
            export.duration = (end_time - start_time) * 1000
            db.session.commit()

            db.session.refresh(export)
            if export.status == ExportStatus.CANCELLED:
                app.logger.warning(
                    "Abort file upload because export was cancelled"
                )
                return

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
