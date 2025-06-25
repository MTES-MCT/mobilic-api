from app.helpers.notification_type import NotificationType

NOTIFICATION_DATA_SCHEMAS = {
    NotificationType.MISSION_CHANGES_WARNING: {
        "mission_id",
        "mission_start_date",
    },
    NotificationType.MISSION_AUTO_VALIDATION: {
        "mission_id",
        "mission_start_date",
        "mission_name",
    },
}


def validate_notification_data(notification_type, data):
    expected_keys = NOTIFICATION_DATA_SCHEMAS.get(notification_type)
    if expected_keys is None:
        return True
    if not isinstance(data, dict):
        raise ValueError("Notification data must be a dict")
    missing = expected_keys - data.keys()
    if missing:
        raise ValueError(f"Missing keys in notification data: {missing}")
    return True
