import os

import logging
from marshmallow import fields
from flask.logging import default_handler
from flask import request, has_request_context
from slacker import Slacker
from logging_ldp.formatters import LDPGELFFormatter
from logging_ldp.handlers import LDPGELFTCPSocketHandler
from logging_ldp.schemas import LDPSchema

from app import app
from app.helpers.authentication import current_user


slack = Slacker(app.config["SLACK_TOKEN"])


def add_request_and_user_context(record):
    try:
        record.current_user = str(current_user)
    except:
        record.current_user = None
    if has_request_context():
        record.device = "{} ({} {})".format(
            request.user_agent.platform,
            request.user_agent.browser,
            request.user_agent.version,
        )
    else:
        record.device = None
    return True


def post_to_slack(message, emoji, color, tuples=None):
    tuples_ = tuples if tuples else []
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": message}},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": "*{}*\n{}".format(tuple[0], tuple[1]),
                }
                for tuple in tuples_
            ],
        },
    ]

    return slack.chat.post_message(
        channel=app.config["SLACK_LOG_CHANNEL"],
        as_user=False,
        username=f"Mobilic backend - {os.environ.get('MOBILIC_ENV', 'test').capitalize()}",
        attachments=[{"blocks": blocks, "color": color}],
        icon_emoji=emoji,
    )


class SlackHandler(logging.Handler):
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
        return post_to_slack(
            self.format(record),
            emoji,
            color,
            [("User", record.current_user), ("Device", record.device)],
        )


class SlackFormatter(logging.Formatter):
    def format(self, record):
        if record.exc_text:
            record.exc_text = None
        return super().format(record)

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


if app.config["SLACK_TOKEN"]:
    slack_handler = SlackHandler()
    slack_handler.addFilter(add_request_and_user_context)
    slack_handler.addFilter(
        lambda r: r.levelno >= logging.WARNING
        or getattr(r, "post_to_slack", False)
    )
    slack_handler.setFormatter(SlackFormatter("%(message)s"))
    logging.getLogger().addHandler(slack_handler)


class FreeSchema(LDPSchema):
    graphql_request = fields.Dict()
    status_code = fields.Int()
    current_user = fields.String()
    device = fields.String()


if app.config["OVH_LDP_TOKEN"]:
    ovh_handler = LDPGELFTCPSocketHandler("gra2.logs.ovh.com")
    ovh_handler.setFormatter(
        LDPGELFFormatter(app.config["OVH_LDP_TOKEN"], schema=FreeSchema)
    )
    logging.getLogger().addHandler(ovh_handler)
