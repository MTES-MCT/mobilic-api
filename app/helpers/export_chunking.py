"""
Utilities for managing Excel export chunking according to business rules.

Chunking rules:
1. > 365 days (regardless of number of employees) → 1 file per calendar year per employee
2. < 365 days AND > 31 days → 1 file per batch of 100 employees per calendar month
3. < 365 days AND < 31 days AND > 100 employees → 1 consolidated file per batch of 100 employees
4. < 365 days AND < 31 days AND < 100 employees → consolidated file OR file per employee (user choice)
"""

from datetime import timedelta, date
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from calendar import monthrange
from app.models import User
from app.helpers.xls.common import clean_string

# Date range thresholds
MAX_DAYS_FOR_YEAR_SPLIT = 365
MAX_DAYS_FOR_MONTH_SPLIT = 31

# User batching
MAX_USERS_PER_BATCH = 100

# Month names for file naming
MONTH_NAMES = {
    1: "janvier",
    2: "fevrier",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "aout",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "decembre",
}


class ExportChunkingStrategy(str, Enum):
    """Export chunking strategies"""

    OVER_365_DAYS = "over_365_days"  # > 365 days
    OVER_31_DAYS = "over_31_days"  # < 365 days and > 31 days
    OVER_100_USERS = "over_100_users"  # < 31 days and > 100 employees
    SINGLE_OR_CONSOLIDATED = (
        "single_or_consolidated"  # < 31 days and < 100 employees
    )


@dataclass
class ExportChunkInfo:
    user_ids: List[int]
    min_date: date
    max_date: date
    file_suffix: str


@dataclass
class ExportChunkingResult:
    strategy: ExportChunkingStrategy
    chunks: List[ExportChunkInfo]


def calculate_days_between(min_date: date, max_date: date) -> int:
    if min_date is None or max_date is None:
        return 0
    return (max_date - min_date).days + 1


def split_into_chunks(items: List, chunk_size: int) -> List[List]:
    return [
        items[i : i + chunk_size] for i in range(0, len(items), chunk_size)
    ]


def _format_user_name(user: User) -> str:
    """Format user name for file suffix."""
    return f"{clean_string(user.last_name)}_{clean_string(user.first_name)}"


def split_date_range_into_years(
    min_date: date, max_date: date
) -> List[Tuple[date, date]]:
    """Split into calendar year periods (1st to last day of each year)."""
    ranges = []
    current_year = min_date.year

    while current_year <= max_date.year:
        # Start of current year chunk
        if current_year == min_date.year:
            chunk_start = min_date
        else:
            chunk_start = date(current_year, 1, 1)

        # End of current year chunk
        if current_year == max_date.year:
            chunk_end = max_date
        else:
            chunk_end = date(current_year, 12, 31)

        ranges.append((chunk_start, chunk_end))
        current_year += 1

    return ranges


def split_date_range_into_months(
    min_date: date, max_date: date
) -> List[Tuple[date, date]]:
    """Split into calendar month periods (1st to last day of each month)."""
    ranges = []
    current_date = min_date

    while current_date <= max_date:
        # Start of current chunk is current_date
        chunk_start = current_date

        # End of current chunk is the last day of this month, or max_date if earlier
        last_day_of_month = monthrange(current_date.year, current_date.month)[
            1
        ]
        chunk_end = date(
            current_date.year, current_date.month, last_day_of_month
        )
        chunk_end = min(chunk_end, max_date)

        ranges.append((chunk_start, chunk_end))

        # Move to first day of next month
        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)

    return ranges


def get_export_chunks(
    user_ids: List[int],
    min_date: date,
    max_date: date,
    one_file_by_employee: bool = False,
) -> ExportChunkingResult:
    """Determine chunking strategy and generate chunks based on date range and user count."""
    num_users = len(user_ids)
    num_days = calculate_days_between(min_date, max_date)

    if num_days >= MAX_DAYS_FOR_YEAR_SPLIT:
        chunks = []
        date_ranges = split_date_range_into_years(min_date, max_date)
        users = User.query.filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in users}

        for user_id in user_ids:
            user = user_map.get(user_id)
            if not user:
                continue

            user_name = _format_user_name(user)

            for start_date, end_date in date_ranges:
                if start_date.year == end_date.year:
                    year_suffix = f"{start_date.year}"
                else:
                    year_suffix = f"{start_date.year}_{end_date.year}"

                suffix = f"{user_name}_{year_suffix}"

                chunks.append(
                    ExportChunkInfo(
                        user_ids=[user_id],
                        min_date=start_date,
                        max_date=end_date,
                        file_suffix=suffix,
                    )
                )

        return ExportChunkingResult(
            strategy=ExportChunkingStrategy.OVER_365_DAYS, chunks=chunks
        )

    if num_days > MAX_DAYS_FOR_MONTH_SPLIT:
        chunks = []
        user_chunks = split_into_chunks(user_ids, MAX_USERS_PER_BATCH)
        date_ranges = split_date_range_into_months(min_date, max_date)

        for user_chunk_idx, user_chunk in enumerate(user_chunks):
            for start_date, end_date in date_ranges:
                user_suffix = (
                    f"batch_{user_chunk_idx + 1}"
                    if len(user_chunks) > 1
                    else ""
                )

                if (
                    start_date.year == end_date.year
                    and start_date.month == end_date.month
                ):
                    date_suffix = (
                        f"{MONTH_NAMES[start_date.month]}_{start_date.year}"
                    )
                else:
                    date_suffix = f"{MONTH_NAMES[start_date.month]}_{start_date.year}_{MONTH_NAMES[end_date.month]}_{end_date.year}"

                suffix_parts = [p for p in [user_suffix, date_suffix] if p]
                suffix = "_".join(suffix_parts) if suffix_parts else "export"

                chunks.append(
                    ExportChunkInfo(
                        user_ids=user_chunk,
                        min_date=start_date,
                        max_date=end_date,
                        file_suffix=suffix,
                    )
                )

        return ExportChunkingResult(
            strategy=ExportChunkingStrategy.OVER_31_DAYS, chunks=chunks
        )

    if num_users > MAX_USERS_PER_BATCH:
        chunks = []
        user_chunks = split_into_chunks(user_ids, MAX_USERS_PER_BATCH)

        for idx, user_chunk in enumerate(user_chunks):
            suffix = f"batch_{idx + 1}" if len(user_chunks) > 1 else "export"
            chunks.append(
                ExportChunkInfo(
                    user_ids=user_chunk,
                    min_date=min_date,
                    max_date=max_date,
                    file_suffix=suffix,
                )
            )

        return ExportChunkingResult(
            strategy=ExportChunkingStrategy.OVER_100_USERS, chunks=chunks
        )

    if one_file_by_employee:
        users = User.query.filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in users}
        chunks = []

        for user_id in user_ids:
            user = user_map.get(user_id)
            if not user:
                continue

            user_name = _format_user_name(user)
            chunks.append(
                ExportChunkInfo(
                    user_ids=[user_id],
                    min_date=min_date,
                    max_date=max_date,
                    file_suffix=user_name,
                )
            )
    else:
        chunks = [
            ExportChunkInfo(
                user_ids=user_ids,
                min_date=min_date,
                max_date=max_date,
                file_suffix="consolide",
            )
        ]

    return ExportChunkingResult(
        strategy=ExportChunkingStrategy.SINGLE_OR_CONSOLIDATED, chunks=chunks
    )
