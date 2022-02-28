from unittest.mock import MagicMock, patch


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
