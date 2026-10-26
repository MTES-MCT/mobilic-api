import json
import os
import unittest

import app.commands  # noqa: F401  (import runs the @cron_monitor decorators)
from app import app
from app.helpers.cron_monitoring import CRON_MONITORS

CRON_JSON = os.path.join(os.path.dirname(__file__), "..", "..", "cron.json")


def _scheduled_crons():
    """Map each flask command scheduled in cron.json to its crontab."""
    with open(CRON_JSON) as f:
        jobs = json.load(f)["jobs"]
    scheduled = {}
    for job in jobs:
        tokens = job["command"].split()
        crontab = " ".join(tokens[:5])
        for part in " ".join(tokens[5:]).split("&&"):
            part_tokens = part.split()
            if "flask" in part_tokens:
                command = part_tokens[part_tokens.index("flask") + 1]
                scheduled[command] = crontab
    return scheduled


class TestCronMonitoring(unittest.TestCase):
    def test_every_scheduled_cron_has_a_monitor(self):
        self.assertEqual(set(_scheduled_crons()), set(CRON_MONITORS))

    def test_monitor_schedules_match_cron_json(self):
        for command, crontab in _scheduled_crons().items():
            self.assertEqual(
                CRON_MONITORS[command]["schedule"],
                {"type": "crontab", "value": crontab},
            )

    def test_all_monitors_are_wired_to_a_command(self):
        monitored = {
            getattr(command.callback, "__cron_monitor_command__", None)
            for command in app.cli.commands.values()
        }
        self.assertEqual(monitored - {None}, set(CRON_MONITORS))
