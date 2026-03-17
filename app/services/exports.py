from datetime import date, timedelta
from app.helpers.celery import async_export_excel, DEFAULT_FILE_NAME
from app.helpers.export_chunking import get_export_chunks


def prepare_export_chunks(users, min_date, max_date, one_file_by_employee):
    users = list(users)
    user_ids = [user.id for user in users]
    user_names = {u.id: (u.first_name, u.last_name) for u in users}

    effective_min_date = (
        min_date if min_date else date.today() - timedelta(days=364)
    )
    effective_max_date = max_date if max_date else date.today()

    return get_export_chunks(
        user_ids=user_ids,
        min_date=effective_min_date,
        max_date=effective_max_date,
        one_file_by_employee=one_file_by_employee,
        user_names=user_names,
    )


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
    chunking_result = prepare_export_chunks(
        users, min_date, max_date, one_file_by_employee
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
