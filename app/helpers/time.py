import datetime
from pytz import timezone

FR_TIMEZONE = timezone("Europe/Paris")


def from_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts)


def to_timestamp(date_time):
    return int(date_time.timestamp())


def utc_to_fr(date_time):
    return date_time.astimezone(FR_TIMEZONE).replace(tzinfo=None)


def get_date_or_today(date=None):
    if not date:
        return datetime.date.today()
    if type(date) is datetime.datetime or isinstance(date, datetime.datetime):
        return date.date()
    return date
