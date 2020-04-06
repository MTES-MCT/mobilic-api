from collections import defaultdict
from dataclasses import dataclass
from typing import List
from datetime import datetime

from app.domain.activity_modifications import build_activity_modification_list
from app.helpers.time import to_timestamp
from app.models import Activity, User, Expenditure, Comment, Mission, Vehicle
from app.models.activity import ActivityType


@dataclass
class WorkDay:
    user: User
    activities: List[Activity]
    expenditures: List[Expenditure]
    comments: List[Comment]
    missions: List[Mission]
    vehicles: List[Vehicle]
    was_modified: bool = False

    @property
    def is_complete(self):
        return (
            self.activities and self.activities[-1].type == ActivityType.REST
        )

    @property
    def start_time(self):
        return self.activities[0].user_time if self.activities else None

    @property
    def end_time(self):
        return self.activities[-1].user_time if self.is_complete else None

    @property
    def activity_timers(self):
        if not self.activities:
            return {}
        timers = defaultdict(lambda: 0)
        end_timestamp = (
            to_timestamp(self.end_time)
            if self.is_complete
            else to_timestamp(datetime.now())
        )
        timers["total_service"] = end_timestamp - to_timestamp(self.start_time)
        for activity, next_activity in zip(
            self.activities[:-1], self.activities[1:]
        ):
            timers[activity.type] += to_timestamp(
                next_activity.user_time
            ) - to_timestamp(activity.user_time)
        if not self.is_complete:
            latest_activity = self.activities[-1]
            timers[latest_activity.type] += end_timestamp - to_timestamp(
                latest_activity.user_time
            )
        timers["total_work"] = (
            timers[ActivityType.DRIVE]
            + timers[ActivityType.WORK]
            + timers[ActivityType.SUPPORT]
        )
        return timers


def group_user_events_by_day(user):
    activities = sorted(
        user.acknowledged_deduplicated_activities, key=lambda e: e.user_time
    )
    expenditures = sorted(
        user.acknowledged_expenditures, key=lambda e: e.event_time
    )
    comments = sorted(user.comments, key=lambda e: e.event_time)

    all_activity_events = sorted(
        build_activity_modification_list(user), key=lambda a: a.event_time
    )
    activity_correction_events = [
        a for a in all_activity_events if not a.is_automatic_or_real_time
    ]

    work_days = []
    current_work_day = None
    for activity in activities:
        if activity.type == ActivityType.REST and current_work_day:
            current_work_day.activities.append(activity)
            work_days.append(current_work_day)
            current_work_day = None
        elif not current_work_day:
            current_work_day = WorkDay(
                user=user,
                activities=[activity],
                expenditures=[],
                comments=[],
                missions=[],
                vehicles=[],
            )
        else:
            current_work_day.activities.append(activity)

    if current_work_day:
        work_days.append(current_work_day)

    for idx, day in enumerate(work_days):
        if idx == 0:
            last_event_time_of_previous_day = datetime.fromtimestamp(0)
        else:
            last_event_time_of_previous_day = (
                work_days[idx - 1].activities[-1].event_time
            )
        if idx == len(work_days) - 1:
            next_day_start_time = datetime.now()
        else:
            next_day_start_time = work_days[idx + 1].start_time
        if day.is_complete:
            day.expenditures = [
                e
                for e in expenditures
                if day.start_time <= e.event_time <= day.end_time
            ]
            day.comments = [
                c
                for c in comments
                if day.start_time <= c.event_time < next_day_start_time
            ]
            day.missions = [
                m
                for m in user.missions
                if day.start_time <= m.user_time < day.end_time
            ]
            day.vehicles = list(
                {
                    vb.vehicle
                    for vb in user.vehicle_bookings
                    if day.start_time <= vb.user_time < day.end_time
                }
            )
            last_event_time_of_the_day = day.activities[-1].event_time
        else:
            last_event_time_of_the_day = datetime.now()

        correction_events_of_the_day = [
            e
            for e in activity_correction_events
            if last_event_time_of_previous_day
            < e.activity_start_time
            <= last_event_time_of_the_day
        ]
        day.was_modified = len(correction_events_of_the_day) > 0

    return work_days
