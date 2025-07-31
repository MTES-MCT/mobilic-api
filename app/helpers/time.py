import calendar
import datetime

from dateutil.relativedelta import relativedelta
from dateutil.tz import gettz
from jours_feries_france import JoursFeries

FR_TIMEZONE = gettz("Europe/Paris")
LOCAL_TIMEZONE = (
    datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
)
VERY_LONG_AGO = datetime.datetime(2000, 1, 1)
VERY_FAR_AHEAD = datetime.datetime(2100, 1, 1)
SUNDAY_WEEKDAY = 6


def from_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts)


def to_timestamp(date_time):
    try:
        return int(date_time.timestamp())
    except (IndexError, AttributeError):
        # Fallback for freezegun compatibility issues with Python 3.11+
        import calendar

        return int(calendar.timegm(date_time.utctimetuple()))


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


def to_datetime(
    dt_or_date,
    tz_for_date=None,
    date_as_end_of_day=False,
    preserve_timezone=False,
):
    if not dt_or_date:
        return dt_or_date
    if isinstance(dt_or_date, datetime.datetime):
        return dt_or_date
    if isinstance(dt_or_date, datetime.date) or isinstance(dt_or_date):
        dt = datetime.datetime(
            dt_or_date.year, dt_or_date.month, dt_or_date.day
        )
        if date_as_end_of_day:
            dt = (
                dt + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
            )
        if tz_for_date:
            if preserve_timezone:
                dt = dt.replace(tzinfo=tz_for_date).astimezone()
            else:
                dt = from_tz(dt, tz_for_date)
        return dt

    if isinstance(dt_or_date, str):
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


def get_daily_periods(start_date_time, end_date_time):
    start_time = start_date_time.time()
    end_time = end_date_time.time()
    inverted = start_time >= end_time
    res = []
    for day in get_dates_range(start_date_time, end_date_time):
        start = day.replace(hour=start_time.hour, minute=start_time.minute)
        end = day.replace(hour=end_time.hour, minute=end_time.minute)
        if inverted:
            end += datetime.timedelta(days=1)
        res.append((start, end))
    return res


def get_first_day_of_week(day):
    day_of_week = day.weekday()
    return day - datetime.timedelta(days=day_of_week)


def get_last_day_of_week(day):
    day_of_week = day.weekday()
    return day + datetime.timedelta(days=SUNDAY_WEEKDAY - day_of_week)


# array_datetime: a list of datetime [d1, d2, d3, ..., dn]
# return: [[s_0, e_0], [s_1, e_1], ..., [s_n, e_n]] a list of date ranges covering the input dates
def get_uninterrupted_datetime_ranges(array_datetime):
    if len(array_datetime) == 0:
        return []

    array_datetime.sort()

    ranges = []
    tmp_start = array_datetime[0]
    tmp_date = array_datetime[0]
    for d in array_datetime[1::]:
        is_day_following = (d - tmp_date).days == 1
        if not is_day_following:
            ranges.append([tmp_start, tmp_date])
            tmp_start = d
        tmp_date = d

    ranges.append([tmp_start, tmp_date])
    return ranges


def end_of_month(date):
    return date.replace(day=calendar.monthrange(date.year, date.month)[1])


def previous_month_period(today):
    previous_month = today + relativedelta(months=-1)
    start = previous_month.replace(day=1)
    end = end_of_month(previous_month)
    return start, end
