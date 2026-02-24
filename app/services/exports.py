from datetime import date
from app.helpers.celery import async_export_excel, DEFAULT_FILE_NAME
from app.helpers.export_chunking import get_export_chunks


def export_activity_report(
    exporter,
    company_ids,
    users,
    min_date,
    max_date,
    one_file_by_employee,
    file_name=None,
    export_type=None,
):
    users = list(users)
    user_ids = [user.id for user in users]

    effective_min_date = min_date if min_date else date(2000, 1, 1)
    effective_max_date = max_date if max_date else date.today()

    chunking_result = get_export_chunks(
        user_ids=user_ids,
        min_date=effective_min_date,
        max_date=effective_max_date,
        one_file_by_employee=one_file_by_employee,
    )

    chunks_data = [
        {
            "user_ids": chunk.user_ids,
            "min_date": chunk.min_date.isoformat(),
            "max_date": chunk.max_date.isoformat(),
            "file_suffix": chunk.file_suffix,
            "strategy": chunking_result.strategy.value,
        }
        for chunk in chunking_result.chunks
    ]

    async_export_excel.delay(
        exporter_id=exporter.id,
        company_ids=company_ids,
        chunks=chunks_data,
        file_name=file_name if file_name is not None else DEFAULT_FILE_NAME,
        export_type=export_type,
    )
