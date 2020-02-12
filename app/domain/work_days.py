from collections import defaultdict
from dataclasses import dataclass
from typing import List

from app.helpers.time import to_timestamp
from app.models import Activity, User, Expenditure
from app.models.activity import ActivityTypes


@dataclass
class WorkDay:
    user: User
    activities: List[Activity]
    expenditures: List[Expenditure]

    @property
    def is_complete(self):
        return (
            self.activities and self.activities[-1].type == ActivityTypes.REST
        )

    @property
    def start_time(self):
        return self.activities[0].event_time if self.activities else None

    @property
    def end_time(self):
        return self.activities[-1].event_time if self.is_complete else None

    @property
    def activity_timers(self):
        timers = defaultdict(lambda: 0)
        timers["total_service"] = to_timestamp(self.end_time) - to_timestamp(
            self.start_time
        )
        for activity, next_activity in zip(
            self.activities[:-1], self.activities[1:]
        ):
            timers[activity.type] += to_timestamp(
                next_activity.event_time
            ) - to_timestamp(activity.event_time)
        return timers

    @property
    def vehicle_registration_number(self):
        return (
            self.activities[0].vehicle_registration_number
            if self.activities
            else None
        )

    @property
    def mission(self):
        return self.activities[0].mission if self.activities else None


def group_user_events_by_day(user):
    activities = sorted(
        user.acknowledged_activities, key=lambda e: e.event_time
    )
    expenditures = sorted(
        user.acknowledged_expenditures, key=lambda e: e.event_time
    )

    work_days = []
    current_work_day = None
    for activity in activities:
        if activity.type == ActivityTypes.REST and current_work_day:
            current_work_day.activities.append(activity)
            work_days.append(current_work_day)
            current_work_day = None
        elif not current_work_day:
            current_work_day = WorkDay(
                user=user, activities=[activity], expenditures=[]
            )
        else:
            current_work_day.activities.append(activity)

    if current_work_day:
        work_days.append(current_work_day)

    for day in work_days:
        if day.is_complete:
            day.expenditures = [
                e
                for e in expenditures
                if day.start_time <= e.event_time <= day.end_time
            ]

    return work_days
