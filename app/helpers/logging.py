import os

import logging
import requests
from marshmallow import fields
from flask.logging import default_handler
from flask import request, has_request_context
from logging_ldp.formatters import LDPGELFFormatter
from logging_ldp.handlers import LDPGELFTCPSocketHandler
from logging_ldp.schemas import LDPSchema

from app import app
from app.helpers.authentication import current_user
from app.helpers.errors import MobilicError


logging.getLogger("googleapicliet.discovery_cache").setLevel(logging.ERROR)


def add_request_and_user_context(record):
    try:
        record.current_user = str(current_user)
        record.email = str(current_user.email)
        record.metabase = f"https://metabase.mobilic.beta.gouv.fr/dashboard/6?id={current_user.id}"
    except:
        record.current_user = None
        record.email = None
        record.metabase = None
    if has_request_context():
        record.endpoint = (
            request.full_path[:-1]
            if request.full_path and request.full_path.endswith("?")
            else request.full_path
        )
        record.device = "{} ({} {})".format(
            request.user_agent.platform,
            request.user_agent.browser,
            request.user_agent.version,
        )
    else:
        record.endpoint = None
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
            username=f"Mobilic backend - {os.environ.get('MOBILIC_ENV', 'test').capitalize()}",
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
                ("User", record.current_user, True),
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
default_handler.addFilter(lambda r: not getattr(r, "graphql_request", False))
default_handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] user=%(current_user)s %(levelname)s in %(name)s: %(message)s"
    )
)


if app.config["MATTERMOST_WEBHOOK"]:
    mattermost_handler = MattermostHandler()
    mattermost_handler.addFilter(add_request_and_user_context)
    mattermost_handler.addFilter(
        lambda r: getattr(
            r,
            "post_to_mattermost",
            r.levelno >= logging.WARNING
            and r.name != "graphql.execution.utils",
        )
    )
    mattermost_handler.setFormatter(MattermostFormatter("%(message)s"))
    logging.getLogger().addHandler(mattermost_handler)


class FreeSchema(LDPSchema):
    graphql_request = fields.Dict()
    status_code = fields.Int()
    response = fields.Dict()
    current_user = fields.String()
    device = fields.String()


if app.config["OVH_LDP_TOKEN"]:
    ovh_handler = LDPGELFTCPSocketHandler("gra2.logs.ovh.com")
    ovh_handler.setFormatter(
        LDPGELFFormatter(app.config["OVH_LDP_TOKEN"], schema=FreeSchema)
    )
    logging.getLogger().addHandler(ovh_handler)
