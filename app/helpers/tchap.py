import json
import uuid

import requests

from app import app

DEFAULT_TCHAP_HOMESERVER = "https://matrix.agent.dev-durable.tchap.gouv.fr"
CHANNELS = {"healthcheck", "interfacage", "crons"}


def _room_for(channel):
    raw_rooms = app.config.get("TCHAP_ROOM_ID")
    if not raw_rooms:
        return None
    try:
        rooms = json.loads(raw_rooms)
    except ValueError:
        rooms = None
    if not isinstance(rooms, dict):
        app.logger.error(
            'TCHAP_ROOM_ID must be a JSON object such as {"healthcheck": "!room:server"}'
        )
        return None
    unknown = set(rooms) - CHANNELS
    if unknown:
        app.logger.error(
            f"TCHAP_ROOM_ID has unknown channels {sorted(unknown)}, expected {sorted(CHANNELS)}"
        )
    return rooms.get(channel)


def send_tchap_message(text, channel, html=None):
    # channel is a key of the TCHAP_ROOM_ID map ("healthcheck", "interfacage",
    # "crons"); a channel without a room is off on this environment.
    # Returns True if the message was actually delivered, False otherwise.
    access_token = app.config.get("TCHAP_ACCESS_TOKEN")
    room_id = _room_for(channel)
    homeserver = app.config.get("TCHAP_HOMESERVER", DEFAULT_TCHAP_HOMESERVER)

    if not access_token or not room_id:
        app.logger.info(
            f"Tchap notification not sent: no token or no room for channel {channel}"
        )
        return False

    txn_id = str(uuid.uuid4())
    content = {"msgtype": "m.text", "body": text}
    if html:
        content["format"] = "org.matrix.custom.html"
        content["formatted_body"] = html

    try:
        response = requests.put(
            f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json=content,
            timeout=10,
        )
        if not response.ok or not response.json().get("event_id"):
            app.logger.error(
                f"Tchap notification failed: {response.status_code} {response.text}"
            )
            return False
        app.logger.info("Tchap notification sent successfully")
        return True
    except Exception as e:
        app.logger.error(f"Tchap notification failed: {e}")
        return False
