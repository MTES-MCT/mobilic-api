from datetime import date
from dataclasses import dataclass
from enum import Enum
from calendar import monthrange
from app.helpers.xls.common import clean_string

MAX_DAYS_FOR_YEAR_SPLIT = 365
MAX_DAYS_FOR_MONTH_SPLIT = 31
MAX_USERS_PER_BATCH = 100

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


def _sort_user_ids(user_ids, user_names):
    if not user_names:
        return sorted(user_ids)
    return sorted(
        user_ids,
        key=lambda uid: (
            (user_names[uid][1].lower(), user_names[uid][0].lower())
            if uid in user_names
            else (str(uid), "")
        ),
    )


class ExportChunkingStrategy(str, Enum):
    OVER_365_DAYS = "over_365_days"
    OVER_31_DAYS = "over_31_days"
    OVER_100_USERS = "over_100_users"
    SINGLE_OR_CONSOLIDATED = "single_or_consolidated"


@dataclass
class ExportChunkInfo:
    user_ids: list
    min_date: date
    max_date: date
    file_suffix: str


@dataclass
class ExportChunkingResult:
    strategy: ExportChunkingStrategy
    chunks: list


def calculate_days_between(min_date, max_date):
    if min_date is None or max_date is None:
        return 0
    return (max_date - min_date).days + 1


def get_strategy_message(strategy, num_users):
    if strategy == ExportChunkingStrategy.OVER_365_DAYS:
        return (
            "La période sélectionnée étant d'au moins 1 an, le téléchargement sera divisé "
            "en plusieurs fichiers pour des raisons techniques. Vous recevrez un fichier par "
            "année et par salarié."
        )

    if strategy == ExportChunkingStrategy.OVER_31_DAYS:
        if num_users > MAX_USERS_PER_BATCH:
            return (
                "Le nombre de salariés sélectionnés étant supérieur à 100 et la période supérieure à 31 jours, "
                "le téléchargement sera divisé en plusieurs fichiers pour des raisons techniques. "
                "Vous recevrez un fichier par mois et par tranche de 100 salariés."
            )
        else:
            return (
                "La période sélectionnée étant supérieure à 31 jours, "
                "le téléchargement sera divisé en plusieurs fichiers pour des raisons techniques. "
                "Vous recevrez un fichier par mois."
            )

    if strategy == ExportChunkingStrategy.OVER_100_USERS:
        return (
            "Le nombre de salariés sélectionnés étant supérieur à 100, le téléchargement sera divisé "
            "en plusieurs fichiers pour des raisons techniques. Vous recevrez un fichier par "
            "tranche de 100 salariés."
        )

    if strategy == ExportChunkingStrategy.SINGLE_OR_CONSOLIDATED:
        return (
            "Vous pouvez choisir un fichier consolidé ou un fichier par salarié en utilisant "
            "le paramètre 'one_file_by_employee' (true pour un fichier par salarié, false ou omis pour un fichier consolidé)."
        )

    return None


def split_into_chunks(items, chunk_size):
    return [
        items[i : i + chunk_size] for i in range(0, len(items), chunk_size)
    ]


def _format_user_name(first_name, last_name):
    return f"{clean_string(last_name)}_{clean_string(first_name)}"


def split_date_range_into_years(min_date, max_date):
    ranges = []
    current_year = min_date.year

    while current_year <= max_date.year:
        if current_year == min_date.year:
            chunk_start = min_date
        else:
            chunk_start = date(current_year, 1, 1)

        if current_year == max_date.year:
            chunk_end = max_date
        else:
            chunk_end = date(current_year, 12, 31)

        ranges.append((chunk_start, chunk_end))
        current_year += 1

    return ranges


def split_date_range_into_months(min_date, max_date):
    ranges = []
    current_date = min_date

    while current_date <= max_date:
        chunk_start = current_date
        last_day_of_month = monthrange(current_date.year, current_date.month)[
            1
        ]
        chunk_end = date(
            current_date.year, current_date.month, last_day_of_month
        )
        chunk_end = min(chunk_end, max_date)

        ranges.append((chunk_start, chunk_end))

        if current_date.month == 12:
            current_date = date(current_date.year + 1, 1, 1)
        else:
            current_date = date(current_date.year, current_date.month + 1, 1)

    return ranges


def _get_user_name(user_id, user_names):
    if user_names and user_id in user_names:
        first_name, last_name = user_names[user_id]
        return _format_user_name(first_name, last_name)
    return f"user_{user_id}"


def _chunk_over_365_days(user_ids, min_date, max_date, user_names):
    """Crée des chunks par année et par salarié, triés alphabétiquement par nom."""
    chunks = []
    date_ranges = split_date_range_into_years(min_date, max_date)
    user_ids_sorted = _sort_user_ids(user_ids, user_names)

    for user_id in user_ids_sorted:
        user_name = _get_user_name(user_id, user_names)

        for start_date, end_date in date_ranges:
            # Format : nom_utilisateur_YYYY pour tri alphabétique puis chronologique
            if start_date.year == end_date.year:
                suffix = f"{user_name}_{start_date.year}"
            else:
                suffix = f"{user_name}_{start_date.year}_{end_date.year}"

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


def _chunk_over_31_days(user_ids, min_date, max_date, user_names=None):
    """Crée des chunks par mois, triés chronologiquement."""
    chunks = []
    user_ids_sorted = _sort_user_ids(user_ids, user_names)
    user_chunks = split_into_chunks(user_ids_sorted, MAX_USERS_PER_BATCH)
    date_ranges = split_date_range_into_months(min_date, max_date)

    # Toujours trier par date puis user pour ordre chronologique
    for start_date, end_date in date_ranges:
        for user_chunk_idx, user_chunk in enumerate(user_chunks):
            chunks.append(
                _make_monthly_chunk(
                    user_chunk,
                    user_chunk_idx,
                    len(user_chunks),
                    start_date,
                    end_date,
                )
            )

    return ExportChunkingResult(
        strategy=ExportChunkingStrategy.OVER_31_DAYS, chunks=chunks
    )


def _make_monthly_chunk(
    user_chunk, user_chunk_idx, total_chunks, start_date, end_date
):
    """Crée un chunk mensuel avec préfixe YYYY-MM pour tri chronologique."""
    user_suffix = f"batch_{user_chunk_idx + 1}" if total_chunks > 1 else ""

    # Préfixe YYYY-MM pour garantir tri chronologique alphabétique
    sort_prefix = f"{start_date.year}-{start_date.month:02d}"

    if start_date.year == end_date.year and start_date.month == end_date.month:
        date_suffix = f"{MONTH_NAMES[start_date.month]}_{start_date.year}"
    else:
        date_suffix = f"{MONTH_NAMES[start_date.month]}_{start_date.year}_{MONTH_NAMES[end_date.month]}_{end_date.year}"

    suffix_parts = [sort_prefix]
    if user_suffix:
        suffix_parts.append(user_suffix)
    suffix_parts.append(date_suffix)
    suffix = "_".join(suffix_parts)

    return ExportChunkInfo(
        user_ids=user_chunk,
        min_date=start_date,
        max_date=end_date,
        file_suffix=suffix,
    )


def _chunk_over_100_users(user_ids, min_date, max_date, user_names=None):
    chunks = []
    user_ids_sorted = _sort_user_ids(user_ids, user_names)
    user_chunks = split_into_chunks(user_ids_sorted, MAX_USERS_PER_BATCH)

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


def _chunk_single_or_consolidated(
    user_ids, min_date, max_date, one_file_by_employee, user_names
):
    if one_file_by_employee:
        chunks = []
        user_ids_sorted = _sort_user_ids(user_ids, user_names)
        for user_id in user_ids_sorted:
            user_name = _get_user_name(user_id, user_names)
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


def get_export_chunks(
    user_ids, min_date, max_date, one_file_by_employee=False, user_names=None
):
    """Calcule les chunks pour l'export avec tri alphabétique des utilisateurs."""
    user_ids = sorted(user_ids)
    num_users = len(user_ids)
    num_days = calculate_days_between(min_date, max_date)

    if num_days >= MAX_DAYS_FOR_YEAR_SPLIT:
        return _chunk_over_365_days(user_ids, min_date, max_date, user_names)

    if num_days > MAX_DAYS_FOR_MONTH_SPLIT:
        return _chunk_over_31_days(user_ids, min_date, max_date, user_names)

    if num_users > MAX_USERS_PER_BATCH:
        return _chunk_over_100_users(user_ids, min_date, max_date, user_names)

    return _chunk_single_or_consolidated(
        user_ids, min_date, max_date, one_file_by_employee, user_names
    )
