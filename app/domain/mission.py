from dateutil.tz import gettz
from sqlalchemy import desc

from app.helpers.submitter_type import SubmitterType
from app.helpers.time import to_tz
from app.models import (
    MissionValidation,
    Mission,
    RegulatoryAlert,
    RegulationCheck,
)
from app.models.location_entry import LocationEntryType
from app.models.regulation_check import RegulationCheckType


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


def get_mission_start_and_end(mission, user):
    activities = mission.activities_for(user=user)
    return get_mission_start_and_end_from_activities(
        activities=activities, user=user
    )


def get_mission_start_and_end_from_activities(activities, user):
    user_timezone = gettz(user.timezone_name)
    mission_start = to_tz(activities[0].start_time, user_timezone).date()
    mission_end = (
        to_tz(activities[-1].end_time, user_timezone).date()
        if to_tz(activities[-1].end_time, user_timezone)
        else None
    )
    return mission_start, mission_end


def get_last_validated_mission_by_user(user):
    last_mission_validation = (
        MissionValidation.query.filter(
            MissionValidation.submitter_id == user.id
        )
        .order_by(desc(MissionValidation.reception_time))
        .first()
    )

    if last_mission_validation is None:
        return last_mission_validation

    return Mission.query.get(last_mission_validation.mission_id)


def had_user_enough_break_last_mission(user):
    last_mission = get_last_validated_mission_by_user(user)

    if last_mission is None:
        return True

    mission_start, mission_end = get_mission_start_and_end(
        mission=last_mission, user=user
    )

    alerts = RegulatoryAlert.query.filter(
        RegulatoryAlert.user == user,
        RegulatoryAlert.day >= mission_start,
        RegulatoryAlert.day <= mission_end,
        RegulatoryAlert.submitter_type == SubmitterType.EMPLOYEE,
        RegulatoryAlert.regulation_check.has(
            RegulationCheck.type == RegulationCheckType.MINIMUM_WORK_DAY_BREAK
        ),
    ).all()

    return len(alerts) == 0
