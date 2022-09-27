from unittest.mock import MagicMock, patch
import datetime

from app.helpers.time import FR_TIMEZONE, from_tz


class AuthenticatedUserContext:
    def __init__(self, user=None):
        self.mocked_authenticated_user = None
        self.mocked_token_verification = None
        if user:
            self.mocked_token_verification = patch(
                "app.helpers.authentication.verify_jwt_in_request",
                new=MagicMock(return_value=None),
            )
            self.mocked_authenticated_user = patch(
                "flask_jwt_extended.utils.get_current_user",
                new=MagicMock(return_value=user),
            )

    def __enter__(self):
        if self.mocked_authenticated_user:
            self.mocked_token_verification.__enter__()
            self.mocked_authenticated_user.__enter__()
        return self

    def __exit__(self, *args):
        if self.mocked_token_verification:
            self.mocked_authenticated_user.__exit__(*args)
            self.mocked_token_verification.__exit__(*args)


def get_date(how_many_days_ago):
    today = datetime.date.today()
    return today - datetime.timedelta(days=how_many_days_ago)


def get_time(how_many_days_ago, hour, minute=0, tz=FR_TIMEZONE):
    day = get_date(how_many_days_ago)
    return get_datetime_tz(day.year, day.month, day.day, hour, minute, tz)


def get_datetime_tz(year, month=1, day=1, hour=0, minutes=0, tz=FR_TIMEZONE):
    return from_tz(datetime.datetime(year, month, day, hour, minutes), tz)
