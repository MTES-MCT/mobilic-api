import datetime


def from_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts / 1000)


def to_timestamp(date_time):
    return int(date_time.timestamp() * 1000)


def local_to_utc(date_time):
    return datetime.datetime.utcfromtimestamp(date_time.timestamp())


def get_date_or_today(date=None):
    if not date:
        return datetime.date.today()
    if type(date) is datetime.datetime or isinstance(date, datetime.datetime):
        return date.date()
    return date
