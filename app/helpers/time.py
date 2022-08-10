import datetime

from dateutil.tz import gettz
from jours_feries_france import JoursFeries

FR_TIMEZONE = gettz("Europe/Paris")
VERY_LONG_AGO = datetime.datetime(2000, 1, 1)
VERY_FAR_AHEAD = datetime.datetime(2100, 1, 1)
SUNDAY_WEEKDAY = 6


def from_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts)


def to_timestamp(date_time):
    return int(date_time.timestamp())


def to_tz(date_time, tz):
    return date_time.astimezone(tz).replace(tzinfo=None)


def from_tz(date_time, tz):
    return date_time.replace(tzinfo=tz).astimezone().replace(tzinfo=None)


def to_fr_tz(date_time):
    return to_tz(date_time, FR_TIMEZONE)


def get_date_or_today(date=None):
    if not date:
        return datetime.date.today()
    if type(date) is datetime.datetime or isinstance(date, datetime.datetime):
        return date.date()
    return date


def to_datetime(dt_or_date, tz_for_date=None, date_as_end_of_day=False):
    if not dt_or_date:
        return dt_or_date
    if type(dt_or_date) is datetime.datetime:
        return dt_or_date
    if type(dt_or_date) is datetime.date:
        dt = datetime.datetime(
            dt_or_date.year, dt_or_date.month, dt_or_date.day
        )
        if date_as_end_of_day:
            dt = (
                dt + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
            )
        if tz_for_date:
            dt = from_tz(dt, tz_for_date)
        return dt

    if type(dt_or_date) is str:
        return datetime.datetime.fromisoformat(dt_or_date)
    return dt_or_date


def _datetime_operator(date_as_end_of_day=False):
    def decorator(op):
        def wrapper(date_or_dt1, date_or_dt2):
            if date_or_dt1 is None:
                return to_datetime(
                    date_or_dt2,
                    date_as_end_of_day=date_as_end_of_day,
                )
            if date_or_dt2 is None:
                return to_datetime(
                    date_or_dt1,
                    date_as_end_of_day=date_as_end_of_day,
                )
            _dt1 = to_datetime(
                date_or_dt1,
                date_as_end_of_day=date_as_end_of_day,
            )
            _dt2 = to_datetime(
                date_or_dt2,
                date_as_end_of_day=date_as_end_of_day,
            )

            return op(_dt1, _dt2)

        return wrapper

    return decorator


@_datetime_operator()
def get_max_datetime(date_or_dt1, date_or_dt2):
    return max(date_or_dt1, date_or_dt2)


@_datetime_operator(date_as_end_of_day=True)
def get_min_datetime(date_or_dt1, date_or_dt2):
    return min(date_or_dt1, date_or_dt2)


def max_or_none(*args):
    args_not_none = [a for a in args if a is not None]
    return max(args_not_none) if args_not_none else None


def min_or_none(*args):
    args_not_none = [a for a in args if a is not None]
    return min(args_not_none) if args_not_none else None


def is_sunday_or_bank_holiday(day):
    return JoursFeries.is_bank_holiday(day) or day.weekday() == SUNDAY_WEEKDAY


def get_dates_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + datetime.timedelta(n)


def get_first_day_of_week(day):
    day_of_week = day.weekday()
    return day - datetime.timedelta(days=day_of_week)


def get_last_day_of_week(day):
    day_of_week = day.weekday()
    return day + datetime.timedelta(days=SUNDAY_WEEKDAY - day_of_week)
