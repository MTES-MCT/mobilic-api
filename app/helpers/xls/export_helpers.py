from typing import List, Dict, Any, Tuple, Callable, Optional
from datetime import date
from io import BytesIO
import zipfile

from app import app
from app.models import User, Company
from app.domain.permissions import ConsultationScope
from app.domain.work_days import group_user_events_by_day_with_limit
from .companies import get_one_excel_file
from .common import clean_string, is_export_empty


def load_work_days_cache(
    all_users: List[User],
    chunks: List[Dict[str, Any]],
    scope: ConsultationScope,
    parse_date_fn: Callable,
) -> Dict[int, List]:
    # Get global date range from all chunks
    global_min_date = min(parse_date_fn(chunk["min_date"]) for chunk in chunks)
    global_max_date = max(parse_date_fn(chunk["max_date"]) for chunk in chunks)

    cache = {}
    for user in all_users:
        work_days, _ = group_user_events_by_day_with_limit(
            user,
            consultation_scope=scope,
            from_date=global_min_date,
            until_date=global_max_date,
            include_dismissed_or_empty_days=True,
        )
        cache[user.id] = work_days

    return cache


def get_work_days_for_users(
    users: List[User],
    cache: Dict[int, List],
    scope: ConsultationScope,
    min_date: date,
    max_date: date,
    one_file_by_employee: bool,
) -> List[Tuple]:
    if cache:
        return _get_work_days_from_cache(
            users, cache, min_date, max_date, one_file_by_employee
        )
    else:
        return _get_work_days_from_db(
            users, scope, min_date, max_date, one_file_by_employee
        )


def _get_work_days_from_cache(
    users: List[User],
    cache: Dict[int, List],
    min_date: date,
    max_date: date,
    one_file_by_employee: bool,
) -> List[Tuple]:
    if one_file_by_employee:
        user_wdays_batches = []
        for user in users:
            cached_work_days = cache.get(user.id, [])
            filtered_work_days = [
                wd for wd in cached_work_days if min_date <= wd.day <= max_date
            ]
            user_wdays_batches.append((user, filtered_work_days))
    else:
        # Consolidated file with all users
        all_users_work_days = []
        for user in users:
            cached_work_days = cache.get(user.id, [])
            filtered_work_days = [
                wd for wd in cached_work_days if min_date <= wd.day <= max_date
            ]
            all_users_work_days += filtered_work_days
        user_wdays_batches = [(None, all_users_work_days)]

    return user_wdays_batches


def _get_work_days_from_db(
    users: List[User],
    scope: ConsultationScope,
    min_date: date,
    max_date: date,
    one_file_by_employee: bool,
) -> List[Tuple]:
    if one_file_by_employee:
        user_wdays_batches = []
        for user in users:
            wdays = group_user_events_by_day_with_limit(
                user,
                consultation_scope=scope,
                from_date=min_date,
                until_date=max_date,
                include_dismissed_or_empty_days=True,
            )[0]
            user_wdays_batches.append((user, wdays))
    else:
        all_users_work_days = []
        for user in users:
            wdays = group_user_events_by_day_with_limit(
                user,
                consultation_scope=scope,
                from_date=min_date,
                until_date=max_date,
                include_dismissed_or_empty_days=True,
            )[0]
            all_users_work_days += wdays
        user_wdays_batches = [(None, all_users_work_days)]

    return user_wdays_batches


def generate_excel_files_from_batch(
    user_wdays_batches: List[Tuple],
    companies: List[Company],
    min_date: date,
    max_date: date,
    file_name: str,
    chunk_suffix: str,
) -> List[Dict[str, Any]]:
    files_data = []

    if len(user_wdays_batches) == 1:
        # Single file (either one user or consolidated)
        wdays = user_wdays_batches[0][1]

        chunk_file_name = file_name
        if chunk_suffix and chunk_suffix not in ("export", "consolide"):
            chunk_file_name = f"{file_name}_{chunk_suffix}"

        # Add suffix if export is empty
        if is_export_empty(wdays):
            chunk_file_name = f"{chunk_file_name}_vide"

        excel_file = get_one_excel_file(wdays, companies, min_date, max_date)
        excel_file.seek(0)

        files_data.append(
            {"name": f"{chunk_file_name}.xlsx", "content": excel_file.read()}
        )
    else:
        # Multiple files (one per user)
        for user, wdays in user_wdays_batches:
            user_name = f"{clean_string(user.last_name)}_{clean_string(user.first_name)}"
            chunk_file_name = f"{file_name}_{user_name}"

            # Add suffix if export is empty for this user
            if is_export_empty(wdays):
                chunk_file_name = f"{chunk_file_name}_vide"

            excel_file = get_one_excel_file(
                wdays, companies, min_date, max_date
            )
            excel_file.seek(0)

            files_data.append(
                {
                    "name": f"{chunk_file_name}.xlsx",
                    "content": excel_file.read(),
                }
            )

    return files_data


def build_final_export(
    files_data: List[Dict[str, Any]],
    file_name: str,
) -> Tuple[bytes, str, str, int]:
    if len(files_data) == 1:
        file_content = files_data[0]["content"]
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        final_file_name = files_data[0]["name"]
        file_size_bytes = len(file_content)

        return file_content, content_type, final_file_name, file_size_bytes

    # Multiple files: create ZIP archive
    memory_file = BytesIO()
    with zipfile.ZipFile(
        memory_file, "w", compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        for file_data in files_data:
            zip_file.writestr(file_data["name"], file_data["content"])

    memory_file.seek(0)
    file_content = memory_file.read()
    content_type = "application/zip"
    final_file_name = f"{file_name}.zip"
    file_size_bytes = len(file_content)

    return file_content, content_type, final_file_name, file_size_bytes
