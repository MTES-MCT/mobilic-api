from enum import Enum


class NotificationType(str, Enum):
    MISSION_CHANGES_WARNING = "mission_changes_warning"
    MISSION_AUTO_VALIDATION = "mission_auto_validation"
