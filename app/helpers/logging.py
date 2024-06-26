import logging
from logging import StreamHandler
from time import time

import requests
import sentry_sdk
from flask import request, g, has_request_context
from flask.logging import default_handler
from logging_ldp.formatters import LDPGELFFormatter
from logging_ldp.handlers import LDPGELFTCPSocketHandler
from logging_ldp.schemas import LDPSchema
from marshmallow import fields
from sentry_sdk import set_tag
from werkzeug.exceptions import HTTPException

from app import app
from app.helpers.authentication import current_user, check_auth
from app.helpers.errors import MobilicError, BadGraphQLRequestError
from config import MOBILIC_ENV

root_logger = logging.getLogger()

COLOR_RESET = "\x1b[0m"
COLOR_GREEN = "\x1b[42m"
COLOR_RED = "\x1b[31m"
COLOR_ORANGE = "\x1b[33m"

SENSITIVE_FIELDS = [
    "password",
    "accessToken",
    "refreshToken",
    "access_token",
    "refresh_token",
]
UNWANTED_FIELDS = ["__typename"]


def _user_info():
    return dict(
        user_name=current_user.display_name if current_user else None,
        user=str(current_user),
        user_id=current_user.id if current_user else None,
        email=str(current_user.email if current_user else None),
        metabase=f"https://metabase.mobilic.beta.gouv.fr/dashboard/6?id={current_user.id}"
        if current_user
        else None,
    )


def _strip_unwanted_and_sensitive_fields_from_log_data(data):
    if not data:
        return data
    if type(data) is dict:
        return {
            k: "***"
            if k in SENSITIVE_FIELDS
            else _strip_unwanted_and_sensitive_fields_from_log_data(v)
            for k, v in data.items()
            if k not in UNWANTED_FIELDS
        }
    if type(data) is list:
        return [
            _strip_unwanted_and_sensitive_fields_from_log_data(i) for i in data
        ]
    return data


def _get_request_endpoint():
    path = (
        request.full_path[:-1]
        if request.full_path and request.full_path.endswith("?")
        else request.full_path
    )
    method_with_path = f"{request.method} {path}"
    graphql_op_short = g.log_info.get("graphql_op_short", "")
    if graphql_op_short:
        return f'{method_with_path} "{graphql_op_short}"'
    return method_with_path


@app.before_request
def store_time_and_request_params():
    try:
        request_json_payload = request.json
    except:
        request_json_payload = {"error": "JSON syntax error"}
    client_id = request.headers.get("X-CLIENT-ID") or ""
    g.log_info = {
        "start_time": time(),
        "vars": request_json_payload,  # by default 'vars' stores the JSON payload of the request, except for GraphQL requests where it's only the GraphQL variables (not the query, see app/helpers/graphql.py).
        "graphql_op": None,
        "json": request_json_payload,
        "graphql_op_short": "",
        "remote_addr": request.remote_addr,
        "referrer": request.referrer,
        "client_id": client_id,
    }
    set_tag("client.id", client_id)


@app.before_request
def enrich_sentry_with_user_information():
    if current_user:
        sentry_sdk.set_user(
            {"id": current_user.id, "email": current_user.email}
        )


@app.after_request
def log_request_info(response):
    if not g.log_info.get("no_log", False) and request.method != "OPTIONS":
        start_time = g.log_info.pop("start_time")
        request_time = round((time() - start_time) * 1000)
        try:
            if (
                response.content_length is not None
                and response.content_length < 10000
            ):
                response_data = response.json
            else:
                response_data = {"not shown": "response too long"}
        except:
            response_data = None

        endpoint = _get_request_endpoint()

        log_title = None
        log_message = endpoint
        log_info = _strip_unwanted_and_sensitive_fields_from_log_data(
            g.log_info
        )

        if response.status_code == 400 and g.log_info.get("is_graphql", False):
            log_title = "Invalid GraphQL request"
            log_message = log_info["json"]
            # Attempt to retrieve current user to augment log info
            try:
                check_auth()
            except:
                pass
            app.logger.error(BadGraphQLRequestError())

        app.logger.info(
            log_message,
            extra={
                "time": request_time,
                "response": _strip_unwanted_and_sensitive_fields_from_log_data(
                    response_data
                ),
                "status_code": response.status_code,
                "size": response.content_length,
                **_user_info(),
                **log_info,
                "endpoint": endpoint,
                "_request_log": True,
                "log_title": log_title,
            },
        )
    return response


def add_request_and_user_context(record):
    try:
        # Make filter idempotent because it might be called several times
        if not getattr(record, "user", False):
            for prop, value in _user_info().items():
                setattr(record, prop, value)
    except:
        setattr(record, "user", None)

    if not getattr(record, "endpoint", False):
        if has_request_context():
            record.endpoint = _get_request_endpoint()
        else:
            record.endpoint = None

    if not getattr(record, "device", False):
        if has_request_context():
            record.device = "{} ({} {})".format(
                request.user_agent.platform,
                request.user_agent.browser,
                request.user_agent.version,
            )
        else:
            record.device = None

    return True


app.logger.setLevel(logging.INFO)
app.logger.addFilter(add_request_and_user_context)

# Disable request loggers (werkzeug for dev and gunicorn for prod)
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("gunicorn.access").setLevel(logging.ERROR)


class TerminalFormatter(logging.Formatter):
    def format(self, record):
        status_color = COLOR_GREEN if record.status_code == 200 else COLOR_RED
        formatter = logging.Formatter(
            f"%(remote_addr)s - - {COLOR_ORANGE}[%(asctime)s]{COLOR_RESET} %(endpoint)s status={status_color}%(status_code)s{COLOR_RESET} time=%(time)sms size=%(size)s - - user=%(user_name)s user_id=%(user_id)s graphql_op=%(graphql_op)s vars=%(vars)s response=%(response).100s... device=%(device)s referrer=%(referrer)s"
        )
        return formatter.format(record)


# Our custom request logger
request_log_handler = StreamHandler()
request_log_handler.addFilter(lambda r: getattr(r, "_request_log", False))
request_log_handler.addFilter(add_request_and_user_context)
request_log_handler.setFormatter(TerminalFormatter())
root_logger.addHandler(request_log_handler)

app.logger.removeHandler(default_handler)

# Stream handler for the rest
other_handler = StreamHandler()
other_handler.addFilter(lambda r: not getattr(r, "_request_log", False))
other_handler.addFilter(add_request_and_user_context)
other_handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] user=%(user)s %(levelname)s in %(name)s: %(message)s"
    )
)
root_logger.addHandler(other_handler)


class OVHLogSchema(LDPSchema):
    json = fields.Dict()
    time = fields.Int(required=True)
    status_code = fields.Int(required=True)
    graphql_op = fields.String()
    response = fields.Dict()
    endpoint = fields.String()
    user_name = fields.String()
    user_id = fields.Int()
    device = fields.String()
    referrer = fields.String(required=False)
    client_id = fields.String(required=False)


if app.config["OVH_LDP_TOKEN"]:
    ovh_handler = LDPGELFTCPSocketHandler("gra2.logs.ovh.com")
    ovh_handler.setFormatter(
        LDPGELFFormatter(app.config["OVH_LDP_TOKEN"], schema=OVHLogSchema)
    )
    root_logger.addHandler(ovh_handler)
