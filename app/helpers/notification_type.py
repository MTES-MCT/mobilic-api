from enum import Enum


class NotificationType(str, Enum):
    MISSION_CHANGES_WARNING = "mission_changes_warning"
    NEW_MISSION_BY_ADMIN = "new_mission_by_admin"
    MISSION_AUTO_VALIDATION = "mission_auto_validation"
