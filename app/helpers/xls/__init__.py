from app import app
from app.helpers.time import FR_TIMEZONE
from app.helpers.xls.signature import retrieve_and_verify_signature

from .companies import get_archive_excel_file
from .common import clean_string
from .export_helpers import (
    load_work_days_cache,
    get_work_days_for_users,
    generate_excel_files_from_batch,
    build_final_export,
)
from app.domain.permissions import ConsultationScope
from app.helpers.export_chunking import ExportChunkingStrategy
from datetime import date


def _parse_date(date_value):
    if isinstance(date_value, str):
        return date.fromisoformat(date_value)
    return date_value


def generate_admin_export_file_from_chunks(
    chunks, users, companies, file_name
):
    strategy = chunks[0].get("strategy") if chunks else None
    company_ids = [c.id for c in companies]
    scope = ConsultationScope(company_ids=company_ids)
    user_map = {u.id: u for u in users}

    cache = {}
    if strategy == ExportChunkingStrategy.OVER_31_DAYS.value:
        cache = load_work_days_cache(users, chunks, scope, _parse_date)

    chunks = sorted(
        chunks,
        key=lambda c: (
            _parse_date(c["min_date"]),
            _parse_date(c["max_date"]),
            c["file_suffix"],
        ),
    )

    files_data = []
    for chunk in chunks:
        chunk_min_date = _parse_date(chunk["min_date"])
        chunk_max_date = _parse_date(chunk["max_date"])
        chunk_user_ids = chunk["user_ids"]
        chunk_suffix = chunk["file_suffix"]

        users = [user_map[uid] for uid in chunk_user_ids if uid in user_map]
        one_file_by_employee = len(chunk_user_ids) == 1

        user_wdays_batches = get_work_days_for_users(
            users,
            cache,
            scope,
            chunk_min_date,
            chunk_max_date,
            one_file_by_employee,
        )

        chunk_files = generate_excel_files_from_batch(
            user_wdays_batches,
            companies,
            chunk_min_date,
            chunk_max_date,
            file_name,
            chunk_suffix,
            all_users=users,
        )
        files_data.extend(chunk_files)

    if not files_data:
        raise ValueError("Aucune donnée à exporter.")

    return build_final_export(files_data, file_name)
