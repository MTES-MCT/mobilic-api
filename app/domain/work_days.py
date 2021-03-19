from collections import defaultdict
from cached_property import cached_property
from dataclasses import dataclass
from typing import List, Set
from datetime import datetime, date, timedelta
from functools import reduce

from app.helpers.time import to_timestamp
from app.models import Activity, User, Mission, Company, Comment
from app.models.activity import ActivityType


def compute_aggregate_durations(periods, min_time=None, max_time=None):
    if not periods:
        return {}
    timers = defaultdict(lambda: 0)
    end_time = periods[-1].end_time if periods[-1].end_time else datetime.now()
    start_time = periods[0].start_time
    if min_time and min_time > start_time:
        start_time = min_time
    if max_time and max_time < end_time:
        end_time = max_time

    end_timestamp = to_timestamp(end_time)

    timers["total_service"] = end_timestamp - to_timestamp(start_time)
    for period in periods:
        timers[period.type] += int(
            period.duration_over(min_time, max_time).total_seconds()
        )

    timers["total_work"] = reduce(
        lambda a, b: a + b, [timers[a_type] for a_type in ActivityType]
    )

    return start_time, end_time, timers


@dataclass(init=False)
class WorkDay:
    day: date
    user: User
    missions: List[Mission]
    companies: Set[Company]
    activities: List[Activity]
    _all_activities: List[Activity]
    comments: List[Comment]

    def __init__(self, user, day):
        self.day = day
        self._are_activities_sorted = True
        self.user = user
        self.missions = []
        self.companies = set()
        self.activities = []
        self._all_activities = []
        self.comments = []
        self._is_complete = True

    def add_mission(self, mission):
        self._are_activities_sorted = False
        self.missions.append(mission)
        self.activities.extend(
            [
                a
                for a in mission.activities_for(self.user)
                if a.start_time <= self._end_of_day
                and (not a.end_time or a.end_time >= self._start_of_day)
            ]
        )
        self.companies.add(mission.company)
        self._all_activities.extend(
            mission.activities_for(
                self.user, include_dismissed_activities=True
            )
        )
        self.comments.extend(mission.acknowledged_comments)

    def _sort_activities(self):
        if not self._are_activities_sorted:
            self.activities.sort(
                key=lambda a: (
                    a.start_time,
                    a.end_time is None,
                    a.reception_time,
                )
            )
            self._all_activities.sort(
                key=lambda a: (
                    a.start_time,
                    a.end_time is None,
                    a.reception_time,
                )
            )
            self._are_activities_sorted = True

    @property
    def is_complete(self):
        return self._is_complete

    @property
    def _start_of_day(self):
        return datetime(self.day.year, self.day.month, self.day.day)

    @property
    def _end_of_day(self):
        return self._start_of_day + timedelta(days=1)

    @property
    def start_time(self):
        self._sort_activities()
        start_of_day = self._start_of_day
        if self.activities:
            return max(self.activities[0].start_time, start_of_day)
        return None

    @property
    def end_time(self):
        self._sort_activities()
        end_of_day = self._end_of_day
        if self.activities:
            acts_end_time = self.activities[-1].end_time
            if acts_end_time:
                return min(acts_end_time, end_of_day)
            if end_of_day >= datetime.now():
                self._is_complete = False
                return None
        return None

    @cached_property
    def expenditures(self):
        expenditures = defaultdict(lambda: 0)
        for mission in self.missions:
            for expenditure in mission.expenditures_for(self.user):
                expenditures[expenditure.type] += 1
        return dict(expenditures)

    @property
    def service_duration(self):
        return self._activity_timers["total_service"]

    @property
    def total_work_duration(self):
        return self._activity_timers["total_work"]

    @property
    def activity_durations(self):
        return {
            a_type: self._activity_timers[a_type] for a_type in ActivityType
        }

    @cached_property
    def _activity_timers(self):
        self._sort_activities()
        return compute_aggregate_durations(
            self.activities, self._start_of_day, self._end_of_day
        )[2]

    @property
    def activity_comments(self):
        all_activity_contexts = [
            ar.context
            for a in self._all_activities
            for ar in a.revisions
            if ar.context is not None
        ]
        all_comments = [
            context.get("comment")
            for context in all_activity_contexts
            if context.get("comment")
        ]
        unique_comments = []
        for comment in all_comments:
            if comment not in unique_comments:
                unique_comments.append(comment)
        return unique_comments

    @property
    def mission_names(self):
        return [m.name for m in self.missions]


class WorkDayStatsOnly:
    day: date
    user: User
    start_time: datetime
    end_time: datetime
    service_duration: int
    total_work_duration: int
    activity_durations: dict
    expenditures: dict
    missions_names: list

    def __init__(
        self,
        day,
        user,
        start_time,
        end_time,
        activity_timers,
        expenditures,
        is_running,
        service_duration,
        total_work_duration,
        mission_names,
    ):
        self.day = day
        self.user = user
        self.start_time = start_time
        self.end_time = end_time if not is_running else None
        self.service_duration = service_duration
        self.total_work_duration = total_work_duration
        self.activity_durations = activity_timers
        self.expenditures = expenditures
        self.mission_names = mission_names


def group_user_events_by_day(
    user, consultation_scope, from_date=None, until_date=None
):
    missions = user.query_missions(
        include_dismissed_activities=True,
        include_revisions=True,
        start_time=from_date,
        end_time=until_date,
    )

    if consultation_scope.company_ids:
        missions = [
            m
            for m in missions
            if m.company_id in consultation_scope.company_ids
        ]

    return group_user_missions_by_day(
        user, missions, from_date=from_date, until_date=until_date
    )


def group_user_missions_by_day(
    user, missions, from_date=None, until_date=None
):
    work_days = []
    current_work_day = None
    current_date = None
    for mission in missions:
        all_mission_activities = mission.activities_for(
            user, include_dismissed_activities=True
        )
        acknowledged_mission_activities = [
            a for a in all_mission_activities if not a.is_dismissed
        ]
        mission_start_time = (
            acknowledged_mission_activities[0].start_time
            if acknowledged_mission_activities
            else all_mission_activities[0].start_time
        )
        mission_start_day = mission_start_time.date()

        mission_end_time = (
            acknowledged_mission_activities[-1].end_time
            if acknowledged_mission_activities
            else None
        ) or datetime.now()

        if not current_date:
            current_date = mission_start_day

        mission_running_day = mission_start_day
        while mission_running_day <= mission_end_time.date():
            if (
                not current_work_day
                or current_work_day.day != mission_running_day
            ):
                current_work_day = WorkDay(user=user, day=mission_running_day)
                work_days.append(current_work_day)
            current_work_day.add_mission(mission)
            mission_running_day += timedelta(days=1)

    if from_date:
        work_days = [w for w in work_days if w.day >= from_date]
    if until_date:
        work_days = [w for w in work_days if w.day <= until_date]
    return work_days
