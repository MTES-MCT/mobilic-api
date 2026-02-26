from base64 import b64decode
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import reduce
from typing import List, Set

from app.domain.history import actions_history
from app.helpers.errors import InvalidParamsError
from app.helpers.time import (
    FR_TIMEZONE,
    from_tz,
    to_datetime,
    to_timestamp,
    to_tz,
    min_or_none,
)
from app.models import Activity, Comment, Company, Mission, User
from app.models.activity import ActivityType
from cached_property import cached_property
from dateutil.tz import gettz
from sqlalchemy import desc


NOT_WORK_ACTIVITIES = [ActivityType.OFF, ActivityType.TRANSFER]


def compute_aggregate_durations(
    periods, include_off_in_service=False, min_time=None, tz=None
):
    max_time = min_time + timedelta(days=1) if min_time else None
    if not periods:
        return {}
    timers = defaultdict(lambda: 0)

    end_time = None
    start_time = None
    timers["total_service"] = 0
    service_periods = (
        [p for p in periods if p.type != ActivityType.OFF]
        if not include_off_in_service
        else periods
    )
    if len(service_periods) > 0:
        end_time = (
            service_periods[-1].end_time
            if service_periods[-1].end_time
            else datetime.now()
        )
        start_time = service_periods[0].start_time
        if min_time and min_time > start_time:
            start_time = min_time
        if max_time and max_time < end_time:
            end_time = max_time

        timers["total_service"] = to_timestamp(end_time) - to_timestamp(
            start_time
        )

    for period in periods:
        total_duration = int(
            period.duration_over(min_time, max_time).total_seconds()
        )
        timers[period.type] += total_duration
        if period.type not in NOT_WORK_ACTIVITIES and min_time:
            user_timezone = gettz(period.user.timezone_name)
            day_duration_tarification = int(
                period.duration_over(
                    from_tz(
                        to_tz(min_time, user_timezone).replace(
                            hour=6, minute=0
                        ),
                        tz,
                    ),
                    from_tz(
                        to_tz(min_time, user_timezone).replace(
                            hour=21, minute=0
                        ),
                        tz,
                    ),
                ).total_seconds()
            )
            timers["night_work_tarification"] += (
                total_duration - day_duration_tarification
            )
            day_duration_legislation = int(
                period.duration_over(
                    from_tz(
                        to_tz(min_time, user_timezone).replace(
                            hour=5, minute=0
                        ),
                        tz,
                    ),
                    from_tz(
                        to_tz(min_time, user_timezone).replace(
                            hour=23,
                            minute=59,
                            second=59,  # Trick used so that night hour appears on the same day
                        ),
                        tz,
                    ),
                ).total_seconds()
            )
            timers["night_work_legislation"] += (
                total_duration - day_duration_legislation
            )

    timers["total_work"] = reduce(
        lambda a, b: a + b,
        [
            timers[a_type]
            for a_type in ActivityType
            if a_type not in NOT_WORK_ACTIVITIES
        ],
    )

    return start_time, end_time, timers


@dataclass(init=False)
class WorkDay:
    day: date
    tz: timezone
    user: User
    missions: List[Mission]
    companies: Set[Company]
    activities: List[Activity]
    _all_activities: List[Activity]
    comments: List[Comment]

    def __init__(self, user, day, tz=FR_TIMEZONE, max_reception_time=None):
        self.day = day
        self.tz = tz
        self._are_activities_sorted = True
        self.user = user
        self.missions = []
        self.companies = set()
        self.activities = []
        self._all_activities = []
        self.comments = []
        self._is_complete = True
        self.max_reception_time = max_reception_time

    def add_mission(self, mission):
        self._are_activities_sorted = False

        # To be commented locally on init regulation alerts only!
        mission.history = actions_history(
            mission, self.user, max_reception_time=self.max_reception_time
        )

        self.missions.append(mission)
        activities = mission.activities_for(
            self.user,
            include_dismissed_activities=True,
            max_reception_time=self.max_reception_time,
        )
        self.activities.extend(
            [
                a
                for a in activities
                if (
                    not a.is_dismissed
                    or (
                        self.max_reception_time
                        and a.dismissed_at > self.max_reception_time
                    )
                )
                and a.start_time < self.end_of_day
                and (not a.end_time or a.end_time > self.start_of_day)
                and a.start_time != a.end_time
            ]
        )
        self.companies.add(mission.company)
        self._all_activities.extend(
            [
                a
                for a in activities
                if a.start_time <= self.end_of_day
                and (not a.end_time or a.end_time >= self.start_of_day)
            ]
        )

        # To be commented locally on init regulation alerts only!
        self.comments.extend(
            mission.retrieve_all_comments(
                max_reception_time=self.max_reception_time
            )
        )

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

    @cached_property
    def start_of_day(self):
        return from_tz(
            datetime(self.day.year, self.day.month, self.day.day), self.tz
        )

    @cached_property
    def end_of_day(self):
        return self.start_of_day + timedelta(days=1)

    def get_start_time(self, include_off_activities=True):
        self._sort_activities()
        start_of_day = self.start_of_day
        activities = (
            self.activities
            if include_off_activities
            else [a for a in self.activities if a.type != ActivityType.OFF]
        )
        if activities:
            return max(activities[0].start_time, start_of_day)
        return None

    def get_end_time(self, include_off_activities=True):
        self._sort_activities()
        end_of_day = self.end_of_day
        activities = (
            self.activities
            if include_off_activities
            else [a for a in self.activities if a.type != ActivityType.OFF]
        )
        if activities:
            acts_end_time = activities[-1].end_time
            if acts_end_time:
                return min(acts_end_time, end_of_day)
            if end_of_day >= datetime.now():
                self._is_complete = False
                return None
        return None

    @property
    def start_time(self):
        return self.get_start_time()

    @property
    def end_time(self):
        return self.get_end_time()

    @cached_property
    def expenditures(self):
        expenditures = defaultdict(lambda: 0)
        for mission in self.missions:
            for expenditure in mission.expenditures_for(
                self.user, max_reception_time=self.max_reception_time
            ):
                if expenditure.spending_date == self.day:
                    expenditures[expenditure.type] += 1
        return dict(expenditures)

    @property
    def service_duration(self):
        return self._activity_timers["total_service"]

    @property
    def total_work_duration(self):
        return self._activity_timers["total_work"]

    @property
    def total_night_work_tarification_duration(self):
        return self._activity_timers["night_work_tarification"]

    @property
    def total_night_work_legislation_duration(self):
        return self._activity_timers["night_work_legislation"]

    @property
    def activity_durations(self):
        return {
            a_type: self._activity_timers[a_type] for a_type in ActivityType
        }

    @cached_property
    def _activity_timers(self):
        self._sort_activities()
        return compute_aggregate_durations(
            self.activities, False, self.start_of_day, self.tz
        )[2]

    @property
    def activity_comments(self):
        all_activity_contexts = [
            ar.context
            for a in self._all_activities
            for ar in a.versions
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

    @cached_property
    def one_and_only_one_vehicle_used(self):
        all_vehicles = set([m.vehicle for m in self.missions])
        return len(all_vehicles) == 1 and all_vehicles.pop() is not None

    @cached_property
    def is_first_mission_overlapping_with_previous_day(self):
        self._sort_activities()
        if not self.activities:
            return False
        first_mission = self.activities[0].mission
        first_mission_start = first_mission.activities_for(
            self.user, max_reception_time=self.max_reception_time
        )[0].start_time
        return first_mission_start < self.start_of_day

    @cached_property
    def is_off_day(self):
        return all([a.type == ActivityType.OFF for a in self.activities])

    @cached_property
    def is_last_mission_overlapping_with_next_day(self):
        self._sort_activities()
        if not self.activities:
            return False
        last_mission = self.activities[-1].mission
        last_mission_end = last_mission.activities_for(
            self.user, max_reception_time=self.max_reception_time
        )[-1].end_time
        return not last_mission_end or last_mission_end > self.end_of_day

    @cached_property
    def start_location(self):
        if (
            not self.activities
            or self.is_first_mission_overlapping_with_previous_day
        ):
            return None
        return self.activities[0].mission.start_location

    @cached_property
    def end_location(self):
        if (
            not self.activities
            or self.is_last_mission_overlapping_with_next_day
        ):
            return None
        return self.activities[-1].mission.end_location_at(
            self.max_reception_time
        )

    @cached_property
    def excel_start_time(self):
        from app.helpers.xls.columns import get_time_format

        if (
            self.is_first_mission_overlapping_with_previous_day
            or self.is_off_day
        ):
            return ("-", "center")
        start_time = self.get_start_time(include_off_activities=False)
        return (
            to_tz(start_time, tz=self.tz) if start_time else None,
            get_time_format(),
        )

    @cached_property
    def excel_end_time(self):
        from app.helpers.xls.columns import get_time_format

        if self.is_last_mission_overlapping_with_next_day or self.is_off_day:
            return ("-", "center")
        end_time = self.get_end_time(include_off_activities=False)
        return (to_tz(end_time, tz=self.tz) if end_time else None, get_time_format())


class WorkDayStatsOnly:
    day: date
    user: User
    start_time: datetime
    last_activity_start_time: datetime
    end_time: datetime
    service_duration: int
    total_work_duration: int
    activity_durations: dict
    expenditures: dict
    missions_names: dict

    def __init__(
        self,
        day,
        user,
        start_time,
        last_activity_start_time,
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
        self.start_time = from_tz(start_time, timezone.utc)
        self.last_activity_start_time = from_tz(
            last_activity_start_time, timezone.utc
        )
        self.end_time = (
            from_tz(end_time, timezone.utc)
            if not is_running and end_time
            else None
        )
        self.service_duration = service_duration
        self.total_work_duration = total_work_duration
        self.activity_durations = activity_timers
        self.expenditures = expenditures
        self.mission_names = mission_names


def group_user_events_by_day_with_limit(
    user,
    consultation_scope=None,
    from_date=None,
    until_date=None,
    tz=FR_TIMEZONE,
    include_holidays=True,
    include_dismissed_or_empty_days=False,
    only_missions_validated_by_admin=False,
    only_missions_validated_by_user=False,
    first=None,
    after=None,
    max_reception_time=None,
    employee_version=False,
):
    if after:
        try:
            max_date = b64decode(after).decode()
            max_date = date.fromisoformat(max_date) - timedelta(days=1)
        except:
            raise InvalidParamsError("Invalid pagination cursor")
        until_date = min(max_date, until_date) if until_date else max_date

    def additional_activity_filters(query):
        query = query.order_by(desc(Activity.start_time), desc(Activity.id))
        if not include_holidays:
            query = query.filter(Activity.type != ActivityType.OFF)
        return query

    missions, has_next = user.query_missions_with_limit(
        include_deleted_missions=True,
        include_revisions=True,  # To be updated locally on init regulation alerts only!
        start_time=to_datetime(from_date, tz_for_date=tz)
        if from_date
        else None,
        end_time=to_datetime(
            until_date, tz_for_date=tz, date_as_end_of_day=True
        )
        if until_date
        else None,
        restrict_to_company_ids=(consultation_scope.company_ids or None)
        if consultation_scope
        else None,
        additional_activity_filters=additional_activity_filters,
        limit_fetch_activities=max(first * 5, 200) if first else None,
        max_reception_time=max_reception_time,
    )

    if only_missions_validated_by_admin:
        missions = [m for m in missions if m.validated_by_admin_for(user)]
    elif only_missions_validated_by_user:
        missions = [
            m
            for m in missions
            if m.validation_of(user, max_reception_time=max_reception_time)
        ]

    work_days = group_user_missions_by_day(
        user,
        missions,
        from_date=from_date,
        until_date=until_date,
        tz=tz,
        include_dismissed_or_empty_days=include_dismissed_or_empty_days,
        max_reception_time=max_reception_time,
        employee_version=employee_version,
    )
    if first and has_next:
        work_days = work_days[1:]
    return work_days, has_next


def group_user_events_by_day_with_limit_both_submitter(
    user,
    consultation_scope=None,
    from_date=None,
    until_date=None,
    tz=FR_TIMEZONE,
    include_dismissed_or_empty_days=False,
    first=None,
    after=None,
    max_reception_time=None,
):
    if after:
        try:
            max_date = b64decode(after).decode()
            max_date = date.fromisoformat(max_date) - timedelta(days=1)
        except:
            raise InvalidParamsError("Invalid pagination cursor")
        until_date = min(max_date, until_date) if until_date else max_date

    missions, has_next = user.query_missions_with_limit(
        include_deleted_missions=True,
        include_revisions=False,
        start_time=to_datetime(from_date, tz_for_date=tz)
        if from_date
        else None,
        end_time=to_datetime(
            until_date, tz_for_date=tz, date_as_end_of_day=True
        )
        if until_date
        else None,
        restrict_to_company_ids=(consultation_scope.company_ids or None)
        if consultation_scope
        else None,
        additional_activity_filters=lambda query: query.order_by(
            desc(Activity.start_time), desc(Activity.id)
        ),
        limit_fetch_activities=max(first * 5, 200) if first else None,
        max_reception_time=max_reception_time,
    )

    missions_validated_by_admin = [
        m for m in missions if m.validated_by_admin_for(user)
    ]
    missions_validated_by_user = [
        m
        for m in missions
        if m.validation_of(user, max_reception_time=max_reception_time)
    ]

    work_days_admin = group_user_missions_by_day(
        user,
        missions_validated_by_admin,
        from_date=from_date,
        until_date=until_date,
        tz=tz,
        include_dismissed_or_empty_days=include_dismissed_or_empty_days,
        max_reception_time=max_reception_time,
    )
    work_days_user = group_user_missions_by_day(
        user,
        missions_validated_by_user,
        from_date=from_date,
        until_date=until_date,
        tz=tz,
        include_dismissed_or_empty_days=include_dismissed_or_empty_days,
        max_reception_time=max_reception_time,
    )
    return work_days_admin, work_days_user


def group_user_missions_by_day(
    user,
    missions,
    from_date=None,
    until_date=None,
    tz=FR_TIMEZONE,
    include_dismissed_or_empty_days=False,
    max_reception_time=None,
    employee_version=False,
):
    work_days = []
    current_work_day = None
    current_date = None
    for mission in missions:
        mission_max_reception_time = max_reception_time
        if employee_version:
            all_user_activities = mission.activities_for(
                user, include_dismissed_activities=True
            )
            latest_user_action_time = mission.get_latest_user_action_time(
                user, all_user_activities
            )
            mission_max_reception_time = min_or_none(
                latest_user_action_time, max_reception_time
            )
        all_mission_activities = mission.activities_for(
            user,
            include_dismissed_activities=True,
            max_reception_time=mission_max_reception_time,
        )
        if all_mission_activities:
            acknowledged_mission_activities = [
                a
                for a in all_mission_activities
                if not a.is_dismissed
                or (
                    mission_max_reception_time
                    and a.dismissed_at > mission_max_reception_time
                )
            ]
            mission_start_time = (
                acknowledged_mission_activities[0].start_time
                if acknowledged_mission_activities
                else all_mission_activities[0].start_time
            )
            mission_start_day = to_tz(mission_start_time, tz).date()

            mission_end_time = (
                acknowledged_mission_activities[-1].end_time
                if acknowledged_mission_activities
                else None
            ) or datetime.now()
            mission_end_day = to_tz(mission_end_time, tz).date()

            if not current_date:
                current_date = mission_start_day

            mission_running_day = mission_start_day
            while mission_running_day <= mission_end_day:
                if (
                    not current_work_day
                    or current_work_day.day != mission_running_day
                ):
                    current_work_day = WorkDay(
                        user=user,
                        day=mission_running_day,
                        tz=tz,
                        max_reception_time=mission_max_reception_time,
                    )
                    work_days.append(current_work_day)
                current_work_day.add_mission(mission)
                mission_running_day += timedelta(days=1)

    if from_date:
        work_days = [w for w in work_days if w.day >= from_date]
    if until_date:
        work_days = [w for w in work_days if w.day <= until_date]
    if not include_dismissed_or_empty_days:
        work_days = [w for w in work_days if w.activities]
    return work_days
