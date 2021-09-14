import logging
from logging import StreamHandler
import requests
from time import time
from marshmallow import fields
import sys
from flask.logging import default_handler
from flask import request, g, has_request_context
from logging_ldp.formatters import LDPGELFFormatter
from logging_ldp.handlers import LDPGELFTCPSocketHandler
from logging_ldp.schemas import LDPSchema

from app import app
from config import MOBILIC_ENV
from app.helpers.authentication import current_user
from app.helpers.errors import MobilicError


logging.getLogger("googleapicliet.discovery_cache").setLevel(logging.ERROR)

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
    g.log_info = {
        "start_time": time(),
        "vars": request.json,
        "graphql_op": None,
        "json": request.json,
        "graphql_op_short": "",
        "remote_addr": request.remote_addr,
        "referrer": request.referrer,
    }


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

        log_func = app.logger.info
        log_title = None
        log_message = endpoint
        log_info = _strip_unwanted_and_sensitive_fields_from_log_data(
            g.log_info
        )

        # For GraphQL request with invalid syntax (error 400) we want to error-log the request info so that it may appear in Mattermost.
        # For other errors we don't need to error-log because the application-level error will be logged at the error level.
        if response.status_code == 400 and g.log_info.get("is_graphql", False):
            log_title = "Invalid GraphQL request"
            log_message = log_info["json"]
            log_func = app.logger.error

        log_func(
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
    # Make filter idempotent because it might be called several times
    if not getattr(record, "user", False):
        for prop, value in _user_info().items():
            setattr(record, prop, value)

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


def post_to_mattermost(
    message, emoji, color, title=None, is_secondary=False, fields_=None
):
    requests.post(
        app.config["MATTERMOST_WEBHOOK"],
        json=dict(
            channel=app.config["MATTERMOST_PRIMARY_LOG_CHANNEL"]
            if not is_secondary
            else app.config["MATTERMOST_SECONDARY_LOG_CHANNEL"],
            username=f"Mobilic backend - {MOBILIC_ENV.capitalize()}",
            icon_emoji=emoji,
            attachments=[
                dict(
                    fallback=title or message,
                    color=color,
                    title=title,
                    text=message,
                    fields=[
                        {"title": f[0], "value": f[1], "short": f[2]}
                        for f in fields_
                    ]
                    if fields_
                    else [],
                )
            ],
        ),
    )


class MattermostHandler(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            emoji = ":rotating_light:"
            color = "#a6343c"
        elif record.levelno >= logging.WARNING:
            emoji = ":warning:"
            color = "#ffba20"
        else:
            emoji = ":information_source:"
            color = "#36a64f"
        em = getattr(record, "emoji", None)
        if em:
            emoji = em

        should_log_to_secondary_channel = getattr(
            record, "to_secondary_slack_channel", None
        )

        if should_log_to_secondary_channel is None:
            should_log_to_secondary_channel = False
            if record.exc_info and type(record.exc_info) is tuple:
                exc_info_class = record.exc_info[0]
                if issubclass(exc_info_class, MobilicError):
                    should_log_to_secondary_channel = not record.exc_info[
                        1
                    ].should_alert_team

        title = getattr(record, "log_title", None)
        if (
            not title
            and record.exc_info
            and type(record.exc_info) is tuple
            and issubclass(record.exc_info[0], MobilicError)
        ):
            title = record.exc_info[0].__name__

        return post_to_mattermost(
            self.format(record),
            emoji,
            color,
            title=title,
            is_secondary=should_log_to_secondary_channel,
            fields_=[
                ("User", record.user, True),
                ("Device", record.device, True),
                ("Email", record.email, True),
                ("Metabase", record.metabase, True),
                ("Endpoint", record.endpoint, True),
            ],
        )


class MattermostFormatter(logging.Formatter):
    def format(self, record):
        s = super().format(record)
        lines = s.split()
        if len(lines) >= 2 and lines[0] == lines[1]:
            return "\n".join([lines[0], *lines[2:]])
        return s

    def formatException(self, ei):
        return f"{ei[1]}"


app.logger.setLevel(logging.INFO)
app.logger.addFilter(add_request_and_user_context)

default_handler.addFilter(lambda r: not getattr(r, "_request_log", False))
default_handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] user=%(user)s %(levelname)s in %(name)s: %(message)s"
    )
)


if MOBILIC_ENV == "dev":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    dev_handler = StreamHandler()
    dev_handler.addFilter(lambda r: getattr(r, "_request_log", False))
    dev_handler.addFilter(add_request_and_user_context)
    dev_handler.setFormatter(
        logging.Formatter(
            "%(remote_addr)s - - [%(asctime)s] %(endpoint)s status=%(status_code)s time=%(time)sms size=%(size)s - - user=%(user_name)s user_id=%(user_id)s graphql_op=%(graphql_op)s vars=%(vars)s response=%(response)s device=%(device)s referrer=%(referrer)s"
        )
    )
    logging.getLogger().addHandler(dev_handler)


if app.config["MATTERMOST_WEBHOOK"]:
    mattermost_handler = MattermostHandler()
    mattermost_handler.addFilter(
        lambda r: getattr(
            r,
            "post_to_mattermost",
            r.levelno >= logging.WARNING
            and r.name != "graphql.execution.utils",
        )
    )
    mattermost_handler.addFilter(add_request_and_user_context)
    mattermost_handler.setFormatter(MattermostFormatter("%(message)s"))
    logging.getLogger().addHandler(mattermost_handler)


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


if app.config["OVH_LDP_TOKEN"]:
    ovh_handler = LDPGELFTCPSocketHandler("gra2.logs.ovh.com")
    ovh_handler.setFormatter(
        LDPGELFFormatter(app.config["OVH_LDP_TOKEN"], schema=OVHLogSchema)
    )
    logging.getLogger().addHandler(ovh_handler)
