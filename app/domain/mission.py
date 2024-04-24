from app.models import User
from app.models.location_entry import LocationEntryType


def get_start_location(location_entries):
    start_location_entries = [
        l
        for l in location_entries
        if l.type == LocationEntryType.MISSION_START_LOCATION
    ]
    return start_location_entries[0] if start_location_entries else None


def get_end_location(location_entries):
    end_location_entries = [
        l
        for l in location_entries
        if l.type == LocationEntryType.MISSION_END_LOCATION
    ]
    return end_location_entries[0] if end_location_entries else None


def is_deleted_from_activities(activities):
    return all(activity.is_dismissed for activity in activities)


def get_start_end_time_at_employee_validation(mission, users_ids):
    ret = dict()
    for user_id in users_ids:
        employee = User.query.get(user_id)
        if not employee:
            continue

        employee_validation = mission.validation_of(user=employee)
        if not employee_validation or not employee_validation.reception_time:
            continue

        activities_at_employee_validation_time = mission.activities_for(
            user=employee,
            max_reception_time=employee_validation.reception_time,
        )
        if len(activities_at_employee_validation_time) == 0:
            continue

        ret[user_id] = (
            activities_at_employee_validation_time[0].start_time,
            activities_at_employee_validation_time[-1].end_time,
        )
    return ret
