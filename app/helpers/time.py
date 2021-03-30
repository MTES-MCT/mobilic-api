import datetime
from dateutil.tz import gettz

FR_TIMEZONE = gettz("Europe/Paris")


def from_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts)


def to_timestamp(date_time):
    return int(date_time.timestamp())


def to_tz(date_time, tz):
    return date_time.astimezone(tz).replace(tzinfo=None)


def to_fr_tz(date_time):
    return to_tz(date_time, FR_TIMEZONE)


def get_date_or_today(date=None):
    if not date:
        return datetime.date.today()
    if type(date) is datetime.datetime or isinstance(date, datetime.datetime):
        return date.date()
    return date


def _datetime_operator(convert_dates_to_end_of_day_times=False):
    def decorator(op):
        def wrapper(date_or_dt1, date_or_dt2):
            if date_or_dt1 is None:
                return date_or_dt2
            if date_or_dt2 is None:
                return date_or_dt1
            _dt1 = date_or_dt1
            _dt2 = date_or_dt2
            if type(_dt1) is datetime.date:
                _dt1 = datetime.datetime(_dt1.year, _dt1.month, _dt1.day)
                if convert_dates_to_end_of_day_times:
                    _dt1 = (
                        _dt1
                        + datetime.timedelta(days=1)
                        - datetime.timedelta(seconds=1)
                    )
            if type(_dt2) is datetime.date:
                _dt2 = datetime.datetime(_dt2.year, _dt2.month, _dt2.day)
                if convert_dates_to_end_of_day_times:
                    _dt2 = (
                        _dt2
                        + datetime.timedelta(days=1)
                        - datetime.timedelta(seconds=1)
                    )

            return op(_dt1, _dt2)

        return wrapper

    return decorator


@_datetime_operator()
def get_max_datetime(date_or_dt1, date_or_dt2):
    return max(date_or_dt1, date_or_dt2)


@_datetime_operator(convert_dates_to_end_of_day_times=True)
def get_min_datetime(date_or_dt1, date_or_dt2):
    return min(date_or_dt1, date_or_dt2)
