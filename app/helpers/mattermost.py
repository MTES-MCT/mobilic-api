import requests

from app import app
from config import MOBILIC_ENV


def send_mattermost_message(thread_title, main_title, main_value, items):
    mattermost_webhook = app.config["MATTERMOST_WEBHOOK"]

    if not mattermost_webhook:
        app.logger.warning(f"No mattermost webhook configured")
        return

    requests.post(
        mattermost_webhook,
        json=dict(
            channel=app.config["MATTERMOST_MAIN_CHANNEL"],
            username=f"{thread_title} - {MOBILIC_ENV.capitalize()}",
            icon_emoji=":robot:",
            attachments=[
                dict(
                    title=main_title,
                    text=main_value,
                    fields=items,
                )
            ],
        ),
    )
