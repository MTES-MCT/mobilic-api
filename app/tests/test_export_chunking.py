from datetime import date
from unittest import TestCase

from app.helpers.export_chunking import (
    get_export_chunks,
    ExportChunkingStrategy,
    calculate_days_between,
    split_into_chunks,
    split_date_range_into_years,
    split_date_range_into_months,
    MAX_DAYS_FOR_YEAR_SPLIT,
    MAX_DAYS_FOR_MONTH_SPLIT,
    MAX_USERS_PER_BATCH,
)


class TestCalculateDaysBetween(TestCase):

    def test_same_day(self):
        d = date(2024, 1, 15)
        self.assertEqual(calculate_days_between(d, d), 1)

    def test_two_consecutive_days(self):
        d1 = date(2024, 1, 15)
        d2 = date(2024, 1, 16)
        self.assertEqual(calculate_days_between(d1, d2), 2)

    def test_one_year(self):
        d1 = date(2024, 1, 1)
        d2 = date(2024, 12, 31)
        # 2024 is leap year
        self.assertEqual(calculate_days_between(d1, d2), 366)

    def test_none_dates(self):
        self.assertEqual(calculate_days_between(None, date(2024, 1, 1)), 0)
        self.assertEqual(calculate_days_between(date(2024, 1, 1), None), 0)


class TestSplitIntoChunks(TestCase):

    def test_empty_list(self):
        self.assertEqual(split_into_chunks([], 10), [])

    def test_exact_chunks(self):
        items = list(range(1, 11))
        chunks = split_into_chunks(items, 5)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0], [1, 2, 3, 4, 5])
        self.assertEqual(chunks[1], [6, 7, 8, 9, 10])

    def test_uneven_chunks(self):
        items = list(range(1, 11))
        chunks = split_into_chunks(items, 3)
        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[0], [1, 2, 3])
        self.assertEqual(chunks[1], [4, 5, 6])
        self.assertEqual(chunks[2], [7, 8, 9])
        self.assertEqual(chunks[3], [10])


class TestSplitDateRangeIntoYears(TestCase):

    def test_single_year(self):
        min_date = date(2024, 3, 15)
        max_date = date(2024, 9, 20)
        ranges = split_date_range_into_years(min_date, max_date)
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0], (date(2024, 3, 15), date(2024, 9, 20)))

    def test_two_complete_years(self):
        min_date = date(2024, 1, 1)
        max_date = date(2025, 12, 31)
        ranges = split_date_range_into_years(min_date, max_date)
        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[0], (date(2024, 1, 1), date(2024, 12, 31)))
        self.assertEqual(ranges[1], (date(2025, 1, 1), date(2025, 12, 31)))

    def test_partial_years(self):
        min_date = date(2024, 11, 15)
        max_date = date(2025, 2, 10)
        ranges = split_date_range_into_years(min_date, max_date)
        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[0], (date(2024, 11, 15), date(2024, 12, 31)))
        self.assertEqual(ranges[1], (date(2025, 1, 1), date(2025, 2, 10)))


class TestSplitDateRangeIntoMonths(TestCase):

    def test_single_month(self):
        min_date = date(2024, 3, 15)
        max_date = date(2024, 3, 20)
        ranges = split_date_range_into_months(min_date, max_date)
        self.assertEqual(len(ranges), 1)
        self.assertEqual(ranges[0], (date(2024, 3, 15), date(2024, 3, 20)))

    def test_two_complete_months(self):
        min_date = date(2024, 1, 1)
        max_date = date(2024, 2, 29)
        ranges = split_date_range_into_months(min_date, max_date)
        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[0], (date(2024, 1, 1), date(2024, 1, 31)))
        self.assertEqual(ranges[1], (date(2024, 2, 1), date(2024, 2, 29)))

    def test_partial_months(self):
        min_date = date(2024, 1, 15)
        max_date = date(2024, 3, 10)
        ranges = split_date_range_into_months(min_date, max_date)
        self.assertEqual(len(ranges), 3)
        self.assertEqual(ranges[0], (date(2024, 1, 15), date(2024, 1, 31)))
        self.assertEqual(ranges[1], (date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(ranges[2], (date(2024, 3, 1), date(2024, 3, 10)))


class TestExportChunkingStrategyOver365Days(TestCase):
    # Strategy triggered when period exceeds MAX_DAYS_FOR_YEAR_SPLIT days

    def test_exactly_365_days(self):
        # Exactly 365 days (non-leap year) → split by year and user
        user_ids = [1, 2]
        min_date = date(2023, 1, 1)
        max_date = date(2023, 12, 31)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(result.strategy, ExportChunkingStrategy.OVER_365_DAYS)
        self.assertEqual(len(result.chunks), 2)
        self.assertEqual(result.chunks[0].user_ids, [1])
        self.assertEqual(result.chunks[0].min_date, date(2023, 1, 1))
        self.assertEqual(result.chunks[0].max_date, date(2023, 12, 31))
        self.assertIn("2023", result.chunks[0].file_suffix)
        self.assertEqual(result.chunks[1].user_ids, [2])

    def test_multiple_years(self):
        user_ids = [1, 2]
        user_names = {1: ("John", "Doe"), 2: ("Jane", "Smith")}
        min_date = date(2023, 6, 15)
        max_date = date(2025, 3, 10)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
            user_names=user_names,
        )

        self.assertEqual(result.strategy, ExportChunkingStrategy.OVER_365_DAYS)
        self.assertEqual(len(result.chunks), 6)  # 2 users × 3 years
        self.assertIn("Doe_John", result.chunks[0].file_suffix)
        self.assertIn("2023", result.chunks[0].file_suffix)

    def test_single_user_multiple_years(self):
        # 2 calendar years but only 150 days → OVER_31_DAYS, not OVER_365_DAYS
        # (150 < MAX_DAYS_FOR_YEAR_SPLIT)
        user_ids = [42]
        user_names = {42: ("Alice", "Wonder")}
        min_date = date(2024, 10, 1)
        max_date = date(2025, 2, 28)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
            user_names=user_names,
        )

        self.assertEqual(result.strategy, ExportChunkingStrategy.OVER_31_DAYS)
        self.assertEqual(len(result.chunks), 5)  # Oct, Nov, Dec, Jan, Feb
        self.assertIn("octobre", result.chunks[0].file_suffix)
        self.assertIn("fevrier", result.chunks[4].file_suffix)


class TestExportChunkingStrategyOver31Days(TestCase):

    def test_two_months(self):
        user_ids = [1, 2, 3]
        min_date = date(2024, 1, 1)
        max_date = date(2024, 2, 29)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(result.strategy, ExportChunkingStrategy.OVER_31_DAYS)
        self.assertEqual(len(result.chunks), 2)
        self.assertEqual(result.chunks[0].user_ids, [1, 2, 3])
        self.assertIn("janvier", result.chunks[0].file_suffix)
        self.assertIn("fevrier", result.chunks[1].file_suffix)

    def test_boundary_32_days(self):
        # 32 days → just above MAX_DAYS_FOR_MONTH_SPLIT threshold
        user_ids = [1]
        min_date = date(2024, 1, 1)
        max_date = date(2024, 2, 1)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(result.strategy, ExportChunkingStrategy.OVER_31_DAYS)
        self.assertEqual(len(result.chunks), 2)

    def test_with_over_100_users(self):
        # 250 users (> MAX_USERS_PER_BATCH) + 2 months → combination of both splits
        user_ids = list(range(1, 251))
        min_date = date(2024, 3, 1)
        max_date = date(2024, 4, 30)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(result.strategy, ExportChunkingStrategy.OVER_31_DAYS)
        self.assertEqual(len(result.chunks), 6)
        # Avec sort_by_date=True: batch1_mars, batch2_mars, batch3_mars, batch1_avril, batch2_avril, batch3_avril
        self.assertEqual(len(result.chunks[0].user_ids), MAX_USERS_PER_BATCH)
        self.assertEqual(len(result.chunks[1].user_ids), MAX_USERS_PER_BATCH)
        self.assertEqual(len(result.chunks[2].user_ids), 50)

    def test_partial_month_ranges(self):
        user_ids = [1, 2]
        min_date = date(2024, 1, 15)
        max_date = date(2024, 3, 10)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(result.strategy, ExportChunkingStrategy.OVER_31_DAYS)
        self.assertEqual(len(result.chunks), 3)
        self.assertEqual(result.chunks[0].min_date, date(2024, 1, 15))
        self.assertEqual(result.chunks[0].max_date, date(2024, 1, 31))
        self.assertEqual(result.chunks[2].min_date, date(2024, 3, 1))
        self.assertEqual(result.chunks[2].max_date, date(2024, 3, 10))


class TestExportChunkingStrategyOver100Users(TestCase):

    def test_exactly_101_users(self):
        # MAX_USERS_PER_BATCH + 1 users → just above threshold, split into 2 batches
        user_ids = list(range(1, MAX_USERS_PER_BATCH + 2))
        min_date = date(2024, 1, 1)
        max_date = date(2024, 1, 15)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.OVER_100_USERS
        )
        self.assertEqual(len(result.chunks), 2)
        self.assertEqual(len(result.chunks[0].user_ids), MAX_USERS_PER_BATCH)
        self.assertEqual(len(result.chunks[1].user_ids), 1)

    def test_250_users(self):
        # 250 users over 20 days → 3 batches of MAX_USERS_PER_BATCH each (last one partial)
        user_ids = list(range(1, 251))
        min_date = date(2024, 5, 1)
        max_date = date(2024, 5, 20)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.OVER_100_USERS
        )
        self.assertEqual(len(result.chunks), 3)  # 3 batches
        self.assertEqual(len(result.chunks[0].user_ids), MAX_USERS_PER_BATCH)
        self.assertEqual(len(result.chunks[1].user_ids), MAX_USERS_PER_BATCH)
        self.assertEqual(len(result.chunks[2].user_ids), 50)

    def test_exactly_31_days_with_101_users(self):
        # Edge case: exactly MAX_DAYS_FOR_MONTH_SPLIT days AND MAX_USERS_PER_BATCH+1 users
        # → OVER_100_USERS takes priority
        user_ids = list(range(1, MAX_USERS_PER_BATCH + 2))
        min_date = date(2024, 1, 1)
        max_date = date(2024, 1, 31)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.OVER_100_USERS
        )
        self.assertEqual(len(result.chunks), 2)


class TestExportChunkingStrategySingleOrConsolidated(TestCase):

    def test_consolidated_file(self):
        user_ids = [1, 2, 3, 4, 5]
        min_date = date(2024, 1, 1)
        max_date = date(2024, 1, 15)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.SINGLE_OR_CONSOLIDATED
        )
        self.assertEqual(len(result.chunks), 1)
        self.assertEqual(result.chunks[0].user_ids, [1, 2, 3, 4, 5])
        self.assertEqual(result.chunks[0].file_suffix, "consolide")

    def test_one_file_per_employee(self):
        user_ids = [1, 2, 3]
        user_names = {
            1: ("Alice", "Smith"),
            2: ("Bob", "Jones"),
            3: ("Carol", "White"),
        }
        min_date = date(2024, 2, 1)
        max_date = date(2024, 2, 10)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=True,
            user_names=user_names,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.SINGLE_OR_CONSOLIDATED
        )
        self.assertEqual(len(result.chunks), 3)
        # Tri alphabétique: Jones, Smith, White
        self.assertEqual(result.chunks[0].user_ids, [2])
        self.assertEqual(result.chunks[1].user_ids, [1])
        self.assertEqual(result.chunks[2].user_ids, [3])
        self.assertIn("Jones_Bob", result.chunks[0].file_suffix)
        self.assertIn("Smith_Alice", result.chunks[1].file_suffix)
        self.assertIn("White_Carol", result.chunks[2].file_suffix)

    def test_single_user(self):
        user_ids = [99]
        user_names = {99: ("Test", "User")}
        min_date = date(2024, 6, 1)
        max_date = date(2024, 6, 5)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
            user_names=user_names,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.SINGLE_OR_CONSOLIDATED
        )
        self.assertEqual(len(result.chunks), 1)
        self.assertEqual(result.chunks[0].user_ids, [99])

    def test_exactly_100_users(self):
        # Exactly MAX_USERS_PER_BATCH → no split by users (threshold at MAX_USERS_PER_BATCH+1)
        user_ids = list(range(1, MAX_USERS_PER_BATCH + 1))
        min_date = date(2024, 1, 1)
        max_date = date(2024, 1, 10)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.SINGLE_OR_CONSOLIDATED
        )
        self.assertEqual(len(result.chunks), 1)
        self.assertEqual(len(result.chunks[0].user_ids), MAX_USERS_PER_BATCH)


class TestExportChunkingEdgeCases(TestCase):

    def test_empty_user_list(self):
        user_ids = []
        min_date = date(2024, 1, 1)
        max_date = date(2024, 1, 31)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.SINGLE_OR_CONSOLIDATED
        )
        self.assertEqual(len(result.chunks), 1)
        self.assertEqual(result.chunks[0].user_ids, [])

    def test_user_names_none(self):
        user_ids = [1, 2]
        min_date = date(2024, 1, 1)
        max_date = date(2024, 1, 10)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=True,
            user_names=None,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.SINGLE_OR_CONSOLIDATED
        )
        self.assertEqual(len(result.chunks), 2)
        self.assertIn("user_1", result.chunks[0].file_suffix)
        self.assertIn("user_2", result.chunks[1].file_suffix)

    def test_missing_user_in_user_names(self):
        user_ids = [1, 2, 3]
        user_names = {1: ("Alice", "Smith"), 2: ("Bob", "Jones")}
        min_date = date(2024, 1, 1)
        max_date = date(2024, 1, 10)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=True,
            user_names=user_names,
        )

        self.assertEqual(len(result.chunks), 3)
        # Tri: "3" < "jones" < "smith" alphabétiquement
        self.assertIn("user_3", result.chunks[0].file_suffix)

    def test_same_date(self):
        user_ids = [1]
        same_date = date(2024, 5, 15)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=same_date,
            max_date=same_date,
            one_file_by_employee=False,
        )

        self.assertEqual(
            result.strategy, ExportChunkingStrategy.SINGLE_OR_CONSOLIDATED
        )
        self.assertEqual(len(result.chunks), 1)

    def test_strategy_priority_order(self):
        # Check strategy priority: OVER_365_DAYS wins even with 200 users
        user_ids = list(range(1, 201))
        min_date = date(2023, 1, 1)
        max_date = date(2024, 12, 31)

        result = get_export_chunks(
            user_ids=user_ids,
            min_date=min_date,
            max_date=max_date,
            one_file_by_employee=False,
        )

        self.assertEqual(result.strategy, ExportChunkingStrategy.OVER_365_DAYS)
