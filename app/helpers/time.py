from datetime import datetime


def from_timestamp(ts):
    return datetime.fromtimestamp(ts / 1000)


def to_timestamp(date_time):
    return int(date_time.timestamp() * 1000)


def local_to_utc(date_time):
    return datetime.utcfromtimestamp(date_time.timestamp())
