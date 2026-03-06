from app import app
from app.helpers.xls.signature import retrieve_and_verify_signature

from .companies import get_one_excel_file, get_archive_excel_file
from .common import clean_string
from .export_helpers import (
    load_work_days_cache,
    get_work_days_for_users,
    generate_excel_files_from_batch,
    build_final_export,
)
from app.models import User, Company
from app.domain.permissions import ConsultationScope
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.export_chunking import ExportChunkingStrategy
from datetime import date
from typing import List, Dict, Any, Tuple


def _parse_date(date_value) -> date:
    """Convert date string to date object if needed."""
    if isinstance(date_value, str):
        return date.fromisoformat(date_value)
    return date_value


def generate_admin_export_file_from_chunks(
    chunks: List[Dict[str, Any]], company_ids: List[int], file_name: str
) -> Tuple[bytes, str, str, int]:
    """Generate Excel files from chunks. Returns ZIP if multiple files."""
    strategy = chunks[0].get("strategy") if chunks else None

    # Setup: load companies and consultation scope
    companies = Company.query.filter(Company.id.in_(company_ids)).all()
    scope = ConsultationScope(company_ids=company_ids)

    # Load all users once to avoid N+1 queries
    all_user_ids = set()
    for chunk in chunks:
        all_user_ids.update(chunk["user_ids"])
    all_users = User.query.filter(User.id.in_(all_user_ids)).all()
    user_map = {u.id: u for u in all_users}

    # Cache work_days for multi-month exports to reduce SQL calls
    # Note: For OVER_365_DAYS, cache is not used because each chunk is specific to
    # one user and one year, so there's no cache reuse across chunks
    cache = {}
    if strategy == ExportChunkingStrategy.OVER_31_DAYS.value:
        cache = load_work_days_cache(all_users, chunks, scope, _parse_date)

    # Process each chunk and generate Excel files
    files_data = []

    for chunk in chunks:
        chunk_min_date = _parse_date(chunk["min_date"])
        chunk_max_date = _parse_date(chunk["max_date"])
        chunk_user_ids = chunk["user_ids"]
        chunk_suffix = chunk["file_suffix"]

        users = [user_map[uid] for uid in chunk_user_ids if uid in user_map]
        one_file_by_employee = len(chunk_user_ids) == 1

        # Get work days (from cache or database)
        user_wdays_batches = get_work_days_for_users(
            users,
            cache,
            scope,
            chunk_min_date,
            chunk_max_date,
            one_file_by_employee,
        )

        # Generate Excel files for this chunk
        chunk_files = generate_excel_files_from_batch(
            user_wdays_batches,
            companies,
            chunk_min_date,
            chunk_max_date,
            file_name,
            chunk_suffix,
        )
        files_data.extend(chunk_files)

    # Build final export (single file or ZIP)
    return build_final_export(files_data, file_name, strategy)


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
