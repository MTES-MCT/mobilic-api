from unittest import TestCase

from app.models.activity import ActivityType
from app.templates.filters import format_activity_type


class TestFormatActivityType(TestCase):
    def test_drive_with_other_task_returns_conduite(self):
        self.assertEqual(
            format_activity_type(ActivityType.DRIVE, allow_other_task=True),
            "Conduite",
        )

    def test_drive_without_other_task_returns_travail(self):
        self.assertEqual(
            format_activity_type(ActivityType.DRIVE, allow_other_task=False),
            "Travail",
        )

    def test_drive_default_returns_travail(self):
        self.assertEqual(
            format_activity_type(ActivityType.DRIVE),
            "Travail",
        )

    def test_work_always_returns_autre_tache(self):
        self.assertEqual(
            format_activity_type(ActivityType.WORK, allow_other_task=True),
            "Autre tâche",
        )
        self.assertEqual(
            format_activity_type(ActivityType.WORK, allow_other_task=False),
            "Autre tâche",
        )

    def test_support_always_returns_accompagnement(self):
        self.assertEqual(
            format_activity_type(ActivityType.SUPPORT),
            "Accompagnement",
        )

    def test_transfer_always_returns_liaison(self):
        self.assertEqual(
            format_activity_type(ActivityType.TRANSFER),
            "Liaison",
        )
