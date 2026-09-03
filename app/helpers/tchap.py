import uuid

import requests

from app import app

TCHAP_HOMESERVER = "https://matrix.agent.dev-durable.tchap.gouv.fr"


def send_tchap_message(text, html=None):
    access_token = app.config.get("TCHAP_ACCESS_TOKEN")
    room_id = app.config.get("TCHAP_ROOM_ID")

    if not access_token or not room_id:
        app.logger.warning(
            "Tchap notification not sent: TCHAP_ACCESS_TOKEN or TCHAP_ROOM_ID not configured"
        )
        return

    txn_id = str(uuid.uuid4())
    content = {"msgtype": "m.text", "body": text}
    if html:
        content["format"] = "org.matrix.custom.html"
        content["formatted_body"] = html

    try:
        response = requests.put(
            f"{TCHAP_HOMESERVER}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json=content,
            timeout=10,
        )
        if not response.ok:
            app.logger.warning(
                f"Tchap notification failed: {response.status_code} {response.text}"
            )
        else:
            app.logger.info("Tchap notification sent successfully")
    except Exception as e:
        app.logger.warning(f"Tchap notification failed: {e}")
