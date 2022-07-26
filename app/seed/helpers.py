from unittest.mock import MagicMock, patch
import datetime


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


def get_time(how_many_days_ago, hour, minute=0):
    day = datetime.date.today() - datetime.timedelta(days=how_many_days_ago)
    hour = datetime.time(hour=hour, minute=minute)
    return datetime.datetime.combine(day, hour)


def get_date(how_many_days_ago):
    today = datetime.date.today()
    return today - datetime.timedelta(days=how_many_days_ago)


def get_dates_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + datetime.timedelta(n)
