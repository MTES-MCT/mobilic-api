from flask_jwt_extended import current_user
import logging
from flask.logging import default_handler
from slacker import Slacker

from app import app


slack = Slacker(app.config["SLACK_TOKEN"])


class LogFormatter(logging.Formatter):
    def format(self, record):
        record.current_user = current_user
        return super().format(record)


formatter = LogFormatter(
    "[%(asctime)s] user=%(current_user)s %(levelname)s in %(name)s: %(message)s"
)


def post_to_slack(message, emoji, color, tuples=None):
    msg = message.replace("\n", " ")
    tuples_ = tuples if tuples else []
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": msg}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*{tuple[0]}*\n{tuple[1]}"}
                for tuple in tuples_
            ],
        },
    ]

    return slack.chat.post_message(
        channel="#mobilic-alerts",
        as_user=False,
        username="Mobilic backend",
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
            emoji = ":information:"
            color = "#36a64f"
        return post_to_slack(
            self.format(record), emoji, color, [("User", current_user)]
        )


class SlackFormatter(logging.Formatter):
    def format(self, record):
        if record.exc_text:
            record.exc_text = None
        return super().format(record)

    def formatException(self, ei):
        return f" : {ei[1]}"


app.logger.setLevel(logging.INFO)
default_handler.setFormatter(formatter)


if app.config["SLACK_TOKEN"]:
    slack_handler = SlackHandler()
    slack_handler.addFilter(
        lambda r: r.levelno >= logging.WARNING
        or getattr(r, "post_to_slack", False)
    )
    slack_handler.setFormatter(SlackFormatter("%(message)s"))
    app.logger.addHandler(slack_handler)
