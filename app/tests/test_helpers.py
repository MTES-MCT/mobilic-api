from datetime import date, datetime
from unittest import TestCase

from app.helpers.time import (
    get_uninterrupted_datetime_ranges,
    previous_month_period,
)


class TestHelper(TestCase):
    def test_datetime_ranges_simple(self):
        dates = [
            datetime(2022, 1, 1),
            datetime(2022, 1, 3),
            datetime(2022, 1, 2),
        ]

        result = get_uninterrupted_datetime_ranges(dates)
        self.assertEquals(1, len(result))
        self.assertEqual(datetime(2022, 1, 1), result[0][0])
        self.assertEqual(datetime(2022, 1, 3), result[0][1])

    def test_datetime_ranges_empty(self):
        dates = []

        result = get_uninterrupted_datetime_ranges(dates)

        self.assertEquals(0, len(result))

    def test_datetime_ranges_one_date(self):
        dates = [
            datetime(2022, 1, 1),
        ]

        result = get_uninterrupted_datetime_ranges(dates)

        self.assertEquals(1, len(result))
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
        self.assertEquals(2, len(result))
        self.assertEqual(datetime(2022, 1, 1), result[0][0])
        self.assertEqual(datetime(2022, 1, 3), result[0][1])
        self.assertEqual(datetime(2022, 1, 6), result[1][0])
        self.assertEqual(datetime(2022, 1, 7), result[1][1])

    def test_previous_month_period(self):
        start, end = previous_month_period(date(2023, 3, 28))
        self.assertEqual(start, date(2023, 2, 1))
        self.assertEqual(end, date(2023, 2, 28))
