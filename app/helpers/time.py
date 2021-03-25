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
