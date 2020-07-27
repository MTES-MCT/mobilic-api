from collections import defaultdict
from cached_property import cached_property
from dataclasses import dataclass
from typing import List
from datetime import datetime

from app.domain.activity_modifications import build_activity_modification_list
from app.helpers.time import to_timestamp
from app.models import Activity, User, Mission
from app.models.activity import ActivityType


@dataclass(init=False)
class WorkDay:
    user: User
    missions: List[Mission]
    _activities: List[Activity]
    _all_activities: List[Activity]
    was_modified: bool

    def __init__(self, user):
        self.user = user
        self.missions = []
        self._activities = []
        self._all_activities = []
        self.was_modified = False

    def add_mission(self, mission):
        self.missions.append(mission)
        self._activities.extend(mission.activities_for(self.user))
        self._all_activities.extend(
            mission.activities_for(
                self.user, include_dismisses_and_revisions=True
            )
        )
        self._activities.sort(key=lambda a: a.start_time)
        self._all_activities.sort(key=lambda a: a.start_time)

    @property
    def is_complete(self):
        return (
            self._activities and self._activities[-1].type == ActivityType.REST
        )

    @property
    def start_time(self):
        if self._activities:
            return self._activities[0].start_time
        if self._all_activities:
            return self._all_activities[0].start_time
        return None

    @property
    def end_time(self):
        return self._activities[-1].start_time if self.is_complete else None

    @cached_property
    def expenditures(self):
        expenditures = defaultdict(lambda: 0)
        for mission in self.missions:
            for expenditure in mission.expenditures_for(self.user):
                expenditures[expenditure.type] += 1
        return dict(expenditures)

    @property
    def activity_timers(self):
        if not self._activities:
            return {}
        timers = defaultdict(lambda: 0)
        end_timestamp = (
            to_timestamp(self.end_time)
            if self.is_complete
            else to_timestamp(datetime.now())
        )
        timers["total_service"] = end_timestamp - to_timestamp(self.start_time)
        for activity, next_activity in zip(
            self._activities[:-1], self._activities[1:]
        ):
            timers[activity.type] += to_timestamp(
                next_activity.start_time
            ) - to_timestamp(activity.start_time)
        if not self.is_complete:
            latest_activity = self._activities[-1]
            timers[latest_activity.type] += end_timestamp - to_timestamp(
                latest_activity.start_time
            )
        timers["total_work"] = (
            timers[ActivityType.DRIVE]
            + timers[ActivityType.WORK]
            + timers[ActivityType.SUPPORT]
        )
        return timers


def group_user_events_by_day(user, consultation_scope):
    missions = user.missions(include_dismisses_and_revisions=True)

    if consultation_scope.company_ids:
        missions = [
            m
            for m in missions
            if m.company_id in consultation_scope.company_ids
        ]

    work_days = []
    current_work_day = None
    for mission in missions:
        all_mission_activities = mission.activities_for(
            user, include_dismisses_and_revisions=True
        )
        acknowledged_mission_activities = [
            a for a in all_mission_activities if a.is_acknowledged
        ]
        mission_start_time = (
            acknowledged_mission_activities[0].start_time
            if acknowledged_mission_activities
            else all_mission_activities[0].start_time
        )
        if (
            not current_work_day
            or current_work_day.start_time.date() != mission_start_time.date()
        ):
            current_work_day = WorkDay(user=user)
            work_days.append(current_work_day)
        current_work_day.add_mission(mission)

        # If no after-time modification was yet detected for the current work day, we check whether the newly added mission introduces some
        if not current_work_day.was_modified:
            all_mission_activity_modifications = build_activity_modification_list(
                all_mission_activities
            )
            if not all(
                [
                    a.is_automatic_or_real_time
                    for a in all_mission_activity_modifications
                ]
            ):
                current_work_day.was_modified = True

    return work_days
