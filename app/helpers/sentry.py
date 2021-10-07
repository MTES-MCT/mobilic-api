import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from werkzeug.exceptions import (
    NotFound,
    MethodNotAllowed,
    HTTPVersionNotSupported,
)
import re

from app import app
from app.helpers.errors import EmailAlreadyRegisteredError, MobilicError
from app.helpers.mail import InvalidEmailAddressError
from config import MOBILIC_ENV


FILTER_OUT_ERRORS = [
    NotFound,
    MethodNotAllowed,
    HTTPVersionNotSupported,
    EmailAlreadyRegisteredError,
    InvalidEmailAddressError,
]


FILTER_OUT_RE_FOR_MOBILIC_ERRORS = [
    re.compile(r"$Wrong email/password combination")
]


def filter_errors(event, hint):
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]
        if any(
            [
                issubclass(exc_type, filtered_out_error_type)
                for filtered_out_error_type in FILTER_OUT_ERRORS
            ]
        ):
            return None
        if issubclass(exc_type, MobilicError) and any(
            [
                regexp.search(exc_value.message) is not None
                for regexp in FILTER_OUT_RE_FOR_MOBILIC_ERRORS
            ]
        ):
            return None
    return event


def setup_sentry():
    sentry_sdk.init(
        dsn=app.config["SENTRY_URL"],
        integrations=[FlaskIntegration()],
        environment=MOBILIC_ENV,
        before_send=filter_errors,
    )
