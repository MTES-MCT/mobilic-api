import requests

from app import app
from config import MOBILIC_ENV


def send_mattermost_message(thread_title, main_title, main_value, items):
    requests.post(
        app.config["MATTERMOST_WEBHOOK"],
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
