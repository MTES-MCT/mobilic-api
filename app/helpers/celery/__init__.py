import time

from celery import Celery
import sentry_sdk

from app import app, db
from app.helpers.s3 import S3Client
from app.helpers.xls import (
    generate_admin_export_file,
    generate_admin_export_file_from_chunks,
)
from app.models import User, Export
from app.models.export import ExportStatus, ExportType

celery = Celery(app.name, broker=app.config["CELERY_BROKER_URL"])
celery.conf.update(app.config)

DEFAULT_FILE_NAME = "rapport_activités"


@celery.task()
def async_export_excel(
    exporter_id,
    company_ids,
    chunks,
    file_name=DEFAULT_FILE_NAME,
    export_type=ExportType.EXCEL,
):
    with app.app_context():
        sentry_sdk.set_tag("feature", "excel_export")

        exporter = User.query.get(exporter_id)

        export = Export(
            user=exporter,
            export_type=export_type,
            context={
                "exporter_id": exporter_id,
                "company_ids": company_ids,
                "chunks": chunks,
            },
        )
        db.session.add(export)
        db.session.commit()

        try:
            start_time = time.perf_counter()
            file_content, content_type, file_name, file_size_bytes = (
                generate_admin_export_file_from_chunks(
                    chunks=chunks,
                    company_ids=company_ids,
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
                    f"Export {export.id} cancelled, aborting file upload"
                )
                return

            path = f"exports/{exporter_id}/{export.id}"
            S3Client.upload_export(file_content, path, content_type)

            export.status = ExportStatus.READY
            export.file_s3_path = path
            export.file_type = content_type
            export.file_name = file_name
            db.session.commit()

            app.logger.info(
                f"Export {export.id} completed: {file_name}, "
                f"{file_size_bytes / 1024:.1f} KB, {export.duration:.0f}ms"
            )

        except Exception as e:
            export.status = ExportStatus.FAILED
            db.session.commit()

            app.logger.error(
                f"Export {export.id} failed for user {exporter_id}",
                exc_info=True,
            )

            raise e
