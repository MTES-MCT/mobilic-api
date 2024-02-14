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
