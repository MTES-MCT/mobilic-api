from contextlib import ExitStack
from unittest.mock import patch

import flask_jwt_extended

from app import app
from app.jobs import platform_health_check

API_TEST_HOST = "http://api.test"


def _post(url, json, headers, timeout):
    # Fresh app context: no stale g.user left by other tests
    with app.app_context():
        response = app.test_client().post(
            url.replace(API_TEST_HOST, ""), json=json, headers=headers
        )
    return type(
        "Resp",
        (),
        {
            "status_code": response.status_code,
            "text": response.get_data(as_text=True),
            "json": lambda self: response.get_json(),
        },
    )()


def route_bot_http_to_test_client():
    """
    Makes the healthcheck bot's real HTTP calls hit the Flask test client.

    Other tests may leave global JWT mocks active (AuthenticatedUserContext
    entered and never exited), so the real JWT functions are restored.
    """
    stack = ExitStack()
    stack.enter_context(patch.dict(app.config, {"API_HOST": API_TEST_HOST}))
    stack.enter_context(
        patch.object(platform_health_check.requests, "post", new=_post)
    )
    stack.enter_context(
        patch(
            "flask_jwt_extended.utils.get_current_user",
            new=flask_jwt_extended.get_current_user,
        )
    )
    stack.enter_context(
        patch(
            "app.helpers.authentication.verify_jwt_in_request",
            new=flask_jwt_extended.verify_jwt_in_request,
        )
    )
    return stack
