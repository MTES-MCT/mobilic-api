import unittest
from unittest.mock import patch

from app import app
from app.helpers.tchap import send_tchap_message

ROOMS = '{"healthcheck": "!hc:tchap", "crons": "!cr:tchap"}'


class TestSendTchapMessage(unittest.TestCase):
    def _send(self, rooms, channel="healthcheck"):
        with patch.dict(
            app.config, {"TCHAP_ACCESS_TOKEN": "token", "TCHAP_ROOM_ID": rooms}
        ), patch("app.helpers.tchap.requests.put") as put:
            put.return_value.ok = True
            put.return_value.json.return_value = {"event_id": "$event"}
            sent = send_tchap_message("hello", channel)
        return sent, put

    def test_sends_to_the_room_of_the_channel(self):
        sent, put = self._send(ROOMS)
        self.assertTrue(sent)
        self.assertIn("/rooms/!hc:tchap/", put.call_args[0][0])

    def test_channel_without_room_is_not_sent(self):
        sent, put = self._send(ROOMS, "interfacage")
        self.assertFalse(sent)
        put.assert_not_called()

    def test_unset_rooms_is_not_sent(self):
        sent, put = self._send(None)
        self.assertFalse(sent)
        put.assert_not_called()

    def test_invalid_rooms_are_logged_and_not_sent(self):
        for rooms in ("!hc:tchap", '["!hc:tchap"]'):
            with self.subTest(rooms=rooms), self.assertLogs(
                app.logger, "ERROR"
            ):
                sent, put = self._send(rooms)
            self.assertFalse(sent)
            put.assert_not_called()

    def test_unknown_channel_key_is_logged(self):
        with self.assertLogs(app.logger, "ERROR"):
            sent, _ = self._send('{"healthcheck": "!hc:tchap", "cron": "!x"}')
        self.assertTrue(sent)

    def test_response_without_event_id_is_a_failure(self):
        with patch.dict(
            app.config, {"TCHAP_ACCESS_TOKEN": "token", "TCHAP_ROOM_ID": ROOMS}
        ), patch("app.helpers.tchap.requests.put") as put:
            put.return_value.ok = True
            put.return_value.json.return_value = {}
            self.assertFalse(send_tchap_message("hello", "healthcheck"))
