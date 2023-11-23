from app.helpers.errors import (
    LogActivityInHolidayMissionError,
    LogHolidayInNotEmptyMissionError,
)


def check_if_mission_holiday(mission):
    if mission.is_holiday():
        raise LogActivityInHolidayMissionError()


def check_log_holiday_only_in_empty_mission(mission):
    if not mission.is_empty():
        raise LogHolidayInNotEmptyMissionError
