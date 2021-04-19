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
from app.helpers.errors import MobilicError

slack = Slacker(app.config["SLACK_TOKEN"])


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
        record.device = "{} ({} {})".format(
            request.user_agent.platform,
            request.user_agent.browser,
            request.user_agent.version,
        )
    else:
        record.device = None
    return True


def post_to_slack(message, emoji, color, is_secondary=False, tuples=None):
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
        channel=app.config["SLACK_PRIMARY_LOG_CHANNEL"]
        if not is_secondary
        else app.config["SLACK_SECONDARY_LOG_CHANNEL"],
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

        return post_to_slack(
            self.format(record),
            emoji,
            color,
            is_secondary=should_log_to_secondary_channel,
            tuples=[
                ("User", record.current_user),
                ("Device", record.device),
                ("Email", record.email),
                ("Metabase", record.metabase),
            ],
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
        lambda r: getattr(
            r,
            "post_to_slack",
            r.levelno >= logging.WARNING
            and r.name != "graphql.execution.utils",
        )
    )
    slack_handler.setFormatter(SlackFormatter("%(message)s"))
    logging.getLogger().addHandler(slack_handler)


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
