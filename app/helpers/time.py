from datetime import datetime, timezone, timedelta


def from_timestamp(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def to_timestamp(date_time):
    aware_date_time = date_time
    if date_time.tzinfo is None:
        aware_date_time = date_time.replace(tzinfo=timezone.utc)
    return aware_date_time.timestamp()
