from collections import defaultdict
from typing import NamedTuple

from app.domain.history import actions_history
from app.helpers.pdf import generate_pdf_from_template, Column
from app.helpers.time import max_or_none
from app.models.activity import ActivityType
from app.templates.filters import (
    format_seconds_duration,
    full_format_day,
    format_expenditures_string_from_count,
)
from datetime import datetime, timedelta


class BreakActivity(NamedTuple):
    start_time: datetime
    end_time: datetime

    @property
    def type(self):
        return "break"

    @property
    def duration(self):
        return self.end_time - self.start_time


def _get_summary_columns(mission):
    columns = [
        Column(
            name="service",
            label="Amplitude",
            color="#CFDAC8",
            format=format_seconds_duration,
        ),
        Column(
            name=ActivityType.DRIVE.value,
            label="Conduite",
            color="#C9CBFF",
            secondary=True,
            format=format_seconds_duration,
        ),
        Column(
            name=ActivityType.WORK.value,
            label="Autre tâche",
            color="#C9CBFF",
            secondary=True,
            format=format_seconds_duration,
        ),
    ]

    if mission.company.require_support_activity:
        columns.append(
            Column(
                name=ActivityType.SUPPORT.value,
                label="Accompagnement",
                color="#C9CBFF",
                secondary=True,
                format=format_seconds_duration,
            )
        )

    columns.extend(
        [
            Column(
                name="break",
                label="Pause",
                color="#C9CBFF",
                secondary=True,
                format=format_seconds_duration,
            ),
            Column(
                name="total_work",
                label="Temps de travail",
                color="#C9CBFF",
                format=format_seconds_duration,
            ),
        ]
    )

    if mission.company.require_expenditures:
        columns.append(
            Column(
                name="expenditures",
                label="Frais",
                color="#FFE5B9",
                format=format_expenditures_string_from_count,
            )
        )
    return columns


def sort_and_fill_with_breaks(activities):
    activities = sorted(activities, key=lambda a: a.start_time)
    activities_with_breaks = []
    for index, activity in enumerate(activities[:-1]):
        activities_with_breaks.append(activity)
        next_activity = activities[index + 1]
        if activity.end_time < next_activity.start_time:
            activities_with_breaks.append(
                BreakActivity(
                    start_time=activity.end_time,
                    end_time=next_activity.start_time,
                )
            )

    if len(activities) > 0:
        activities_with_breaks.append(activities[-1])
    return activities_with_breaks


def generate_mission_details_pdf(
    mission, user, show_history_before_employee_validation=True
):
    mission_name = mission.name
    mission_subtitle = None

    activities = mission.activities_for(user)
    all_user_activities = mission.activities_for(
        user, include_dismissed_activities=True
    )

    show_dates = (
        min(
            [
                min([v.start_time for v in a.versions])
                for a in all_user_activities
            ]
        ).date()
        != max_or_none(
            *[
                max_or_none(*[v.end_time for v in a.versions if v.end_time])
                for a in all_user_activities
            ]
        ).date()
    )

    if mission_name:
        mission_name = f"Mission : {mission_name}"
        mission_subtitle = f"Journée du {full_format_day((activities or all_user_activities)[0].start_time)}"
    else:
        mission_name = f"Mission du {full_format_day((activities or all_user_activities)[0].start_time)}"

    activities_with_breaks = sort_and_fill_with_breaks(activities)
    stats = defaultdict(lambda: timedelta(0))
    for activity_or_break in activities_with_breaks:
        stats[activity_or_break.type] += activity_or_break.duration
        stats["service"] += activity_or_break.duration
        if type(activity_or_break.type) is ActivityType:
            stats["total_work"] += activity_or_break.duration

    stats["expenditures"] = defaultdict(lambda: 0)
    for expenditure in mission.expenditures_for(user):
        stats["expenditures"][expenditure.type] += 1

    return generate_pdf_from_template(
        "mission_details_pdf.html",
        mission_name=mission_name,
        mission_subtitle=mission_subtitle,
        company_name=mission.company.name,
        vehicle_name=mission.vehicle.registration_number
        if mission.vehicle
        else None,
        user=user,
        show_dates=show_dates,
        start_time=activities[0].start_time,
        end_time=activities[-1].end_time,
        start_location=mission.start_location.address.format()
        if mission.start_location
        else None,
        end_location=mission.end_location.address.format()
        if mission.end_location
        else None,
        start_kilometer_reading=mission.start_location.kilometer_reading
        if mission.start_location
        else None,
        end_kilometer_reading=mission.end_location.kilometer_reading
        if mission.end_location
        else None,
        columns=_get_summary_columns(mission),
        stats=stats,
        activities=sort_and_fill_with_breaks(activities),
        show_history_before_employee_validation=show_history_before_employee_validation,
        comments=sorted(
            [c for c in mission.comments if not c.is_dismissed],
            key=lambda c: c.reception_time,
        ),
        actions=actions_history(
            mission, user, show_history_before_employee_validation
        ),
    )
