from datetime import date, datetime
from unittest import TestCase

from app.helpers.time import (
    get_uninterrupted_datetime_ranges,
    previous_month_period,
    get_daily_periods,
)


class TestHelper(TestCase):
    def test_datetime_ranges_simple(self):
        dates = [
            datetime(2022, 1, 1),
            datetime(2022, 1, 3),
            datetime(2022, 1, 2),
        ]

        result = get_uninterrupted_datetime_ranges(dates)
        self.assertEqual(1, len(result))
        self.assertEqual(datetime(2022, 1, 1), result[0][0])
        self.assertEqual(datetime(2022, 1, 3), result[0][1])

    def test_datetime_ranges_empty(self):
        dates = []

        result = get_uninterrupted_datetime_ranges(dates)

        self.assertEqual(0, len(result))

    def test_datetime_ranges_one_date(self):
        dates = [
            datetime(2022, 1, 1),
        ]

        result = get_uninterrupted_datetime_ranges(dates)

        self.assertEqual(1, len(result))
        self.assertEqual(datetime(2022, 1, 1), result[0][0])
        self.assertEqual(datetime(2022, 1, 1), result[0][1])

    def test_datetime_ranges_simple(self):
        dates = [
            datetime(2022, 1, 1),
            datetime(2022, 1, 3),
            datetime(2022, 1, 2),
            datetime(2022, 1, 6),
            datetime(2022, 1, 7),
        ]

        result = get_uninterrupted_datetime_ranges(dates)
        self.assertEqual(2, len(result))
        self.assertEqual(datetime(2022, 1, 1), result[0][0])
        self.assertEqual(datetime(2022, 1, 3), result[0][1])
        self.assertEqual(datetime(2022, 1, 6), result[1][0])
        self.assertEqual(datetime(2022, 1, 7), result[1][1])

    def test_previous_month_period(self):
        start, end = previous_month_period(date(2023, 3, 28))
        self.assertEqual(start, date(2023, 2, 1))
        self.assertEqual(end, date(2023, 2, 28))

    def test_daily_periods(self):
        start_date_time = datetime(2023, 2, 1, 8, 30)
        end_date_time = datetime(2023, 2, 8, 17, 00)
        periods = get_daily_periods(
            start_date_time=start_date_time, end_date_time=end_date_time
        )
        self.assertEqual(8, len(periods))
        self.assertEqual(periods[0][0].hour, 8)
        self.assertEqual(periods[0][1].hour, 17)
        self.assertEqual(periods[1][0].hour, 8)
        self.assertEqual(periods[1][1].hour, 17)
        self.assertEqual(periods[-1][0].day, 8)
        self.assertEqual(periods[-1][1].day, 8)

    def test_daily_periods_one_date(self):
        start_date_time = datetime(2023, 2, 1, 8, 30)
        end_date_time = datetime(2023, 2, 1, 17, 00)
        periods = get_daily_periods(
            start_date_time=start_date_time, end_date_time=end_date_time
        )
        self.assertEqual(1, len(periods))
        self.assertEqual(periods[0][0].hour, 8)
        self.assertEqual(periods[0][1].hour, 17)

    def test_daily_periods_one_start_hour_after_end_hour(self):
        start_date_time = datetime(2023, 2, 1, 17, 30)
        end_date_time = datetime(2023, 2, 3, 8, 0)
        periods = get_daily_periods(
            start_date_time=start_date_time, end_date_time=end_date_time
        )
        self.assertEqual(2, len(periods))
        self.assertEqual(periods[0][0].hour, 17)
        self.assertEqual(periods[0][1].hour, 8)
        self.assertEqual(periods[0][0].day, 1)
        self.assertEqual(periods[0][1].day, 2)
        self.assertEqual(periods[-1][0].hour, 17)
        self.assertEqual(periods[-1][1].hour, 8)
        self.assertEqual(periods[-1][0].day, 2)
        self.assertEqual(periods[-1][1].day, 3)
