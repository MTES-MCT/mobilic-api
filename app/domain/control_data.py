import datetime
import pytz
from app.models import User

EXTRA_DATETIME_FIELDS = [
    "breach_period_start",
    "breach_period_end",
    "work_range_start",
    "work_range_end",
    "longest_uninterrupted_work_start",
    "longest_uninterrupted_work_end",
]


def convert_extra_datetime_to_user_tz(extra, user_id):
    if not any(key in extra for key in EXTRA_DATETIME_FIELDS):
        return

    controlled_user = User.query.filter(User.id == user_id).one()
    timezone = pytz.timezone(controlled_user.timezone_name)

    for key in EXTRA_DATETIME_FIELDS:
        if key not in extra:
            continue
        datetime_utc_str = extra.get(key)
        datetime_utc = datetime.datetime.fromisoformat(
            datetime_utc_str
        ).replace(tzinfo=datetime.timezone.utc)
        datetime_tz = datetime_utc.astimezone(timezone)
        extra[key] = datetime_tz.strftime("%Y-%m-%dT%H:%M:%S")
