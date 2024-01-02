from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum

from app import db
from app.helpers.frozen_version_utils import (
    filter_out_future_events,
    freeze_activities,
)
from app.helpers.time import max_or_none
from app.models.activity import ActivityType
from app.models.event import EventBaseModel


class UserMissionModificationStatus(str, Enum):
    USER_MODIFIED_LAST = "user_modified_last"
    OTHERS_MODIFIED_AFTER_USER = "other_modified_after_user"
    ONLY_OTHERS_ACTIONS = "only_others_actions"
    NO_DATA_FOR_USER = "no_data_for_user"


class Mission(EventBaseModel):
    backref_base_name = "missions"

    name = db.Column(db.TEXT, nullable=True)

    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref="missions")

    context = db.Column(JSONB(none_as_null=True), nullable=True)

    vehicle_id = db.Column(
        db.Integer, db.ForeignKey("vehicle.id"), nullable=True
    )
    vehicle = db.relationship("Vehicle", backref="missions")

    def activities_for(
        self, user, include_dismissed_activities=False, max_reception_time=None
    ):
        all_activities_for_user = sorted(
            [a for a in self.activities if a.user_id == user.id],
            key=lambda a: a.start_time,
        )
        if max_reception_time:
            all_activities_for_user = freeze_activities(
                all_activities_for_user, max_reception_time
            )
        if not include_dismissed_activities:
            if max_reception_time:
                return [
                    a
                    for a in all_activities_for_user
                    if not a.is_dismissed
                    or a.dismissed_at > max_reception_time
                ]
            else:
                return [
                    a for a in all_activities_for_user if not a.is_dismissed
                ]
        return all_activities_for_user

    def current_activity_at_time_for_user(self, user, date_time):
        for activity in self.activities_for(user):
            if activity.start_time <= date_time and (
                not activity.end_time or activity.end_time > date_time
            ):
                return activity
        return None

    def expenditures_for(
        self,
        user,
        include_dismissed_expenditures=False,
        max_reception_time=None,
    ):
        expenditures_for_user = [
            e
            for e in self.expenditures
            if e.user_id == user.id
            and (include_dismissed_expenditures or not e.is_dismissed)
        ]
        if max_reception_time:
            return filter_out_future_events(
                expenditures_for_user, max_reception_time
            )
        return expenditures_for_user

    def validations_for(self, user, max_reception_time=None):
        validations_for_user = [
            v
            for v in self.validations
            if v.user_id == user.id or (not v.user_id and v.is_admin)
        ]
        if max_reception_time:
            return filter_out_future_events(
                validations_for_user, max_reception_time
            )
        return validations_for_user

    def retrieve_all_comments(self, max_reception_time=None):
        if max_reception_time:
            return filter_out_future_events(self.comments, max_reception_time)
        return self.comments

    @property
    def acknowledged_activities(self):
        return sorted(
            [a for a in self.activities if not a.is_dismissed],
            key=lambda a: (a.start_time, a.id),
        )

    @property
    def acknowledged_expenditures(self):
        return sorted(
            [e for e in self.expenditures if not e.is_dismissed],
            key=lambda e: e.reception_time,
        )

    @property
    def acknowledged_comments(self):
        return sorted(
            [c for c in self.comments if not c.is_dismissed],
            key=lambda c: c.reception_time,
        )

    @property
    def start_location(self):
        from app.models.location_entry import LocationEntryType

        start_location_entry = [
            l
            for l in self.location_entries
            if l.type == LocationEntryType.MISSION_START_LOCATION
        ]
        return start_location_entry[0] if start_location_entry else None

    def end_location_at(self, max_reception_time):
        from app.models.location_entry import LocationEntryType

        location_entries = (
            filter_out_future_events(self.location_entries, max_reception_time)
            if max_reception_time
            else self.location_entries
        )
        end_location_entry = [
            l
            for l in location_entries
            if l.type == LocationEntryType.MISSION_END_LOCATION
        ]
        return end_location_entry[0] if end_location_entry else None

    @property
    def end_location(self):
        from app.models.location_entry import LocationEntryType

        end_location_entry = [
            l
            for l in self.location_entries
            if l.type == LocationEntryType.MISSION_END_LOCATION
        ]
        return end_location_entry[0] if end_location_entry else None

    def validation_of(self, user, max_reception_time=None):
        validations_of_user_for_himself_or_all = [
            v
            for v in self.validations
            if v.submitter_id == user.id
            and (v.user_id is None or v.user_id == user.id)
        ]
        if max_reception_time:
            validations_of_user_for_himself_or_all = filter_out_future_events(
                validations_of_user_for_himself_or_all, max_reception_time
            )
        if len(validations_of_user_for_himself_or_all) == 2:
            return [
                v for v in validations_of_user_for_himself_or_all if v.user_id
            ][0]
        return (
            validations_of_user_for_himself_or_all[0]
            if validations_of_user_for_himself_or_all
            else None
        )

    @property
    def validated_by_admin(self):
        return any([v.is_admin and not v.user_id for v in self.validations])

    def first_validation_time_by_admin(self):
        admin_validation_times = [
            v.reception_time for v in self.validations if v.is_admin
        ]
        if len(admin_validation_times) == 0:
            return None
        return min(admin_validation_times)

    def validated_by_admin_for(self, user):
        return any(
            [
                v.is_admin and (not v.user_id or v.user_id == user.id)
                for v in self.validations
            ]
        )

    def modification_status_and_latest_action_time_for_user(self, user):
        all_user_activities = self.activities_for(
            user, include_dismissed_activities=True
        )
        if not all_user_activities:
            return UserMissionModificationStatus.NO_DATA_FOR_USER, None

        latest_user_action_time = self.get_latest_user_action_time(
            user, all_user_activities
        )

        if not latest_user_action_time:
            # Mission was most likely created by the admin, user is not yet informed of it
            activities = [a for a in all_user_activities if not a.is_dismissed]
            if activities:
                return UserMissionModificationStatus.ONLY_OTHERS_ACTIONS, None
            return UserMissionModificationStatus.NO_DATA_FOR_USER, None

        return (
            UserMissionModificationStatus.OTHERS_MODIFIED_AFTER_USER
            if any(
                [
                    activity.last_update_time > latest_user_action_time
                    for activity in all_user_activities
                ]
            )
            else UserMissionModificationStatus.USER_MODIFIED_LAST,
            latest_user_action_time,
        )

    def get_latest_user_action_time(self, user, all_user_activities):
        user_validation = self.validation_of(user)
        latest_user_action_time = (
            user_validation.reception_time if user_validation else None
        )
        if not latest_user_action_time:
            latest_user_action_time = max_or_none(
                *[
                    a.latest_modification_time_by(user)
                    for a in all_user_activities
                ]
            )
        return latest_user_action_time

    def ended_for(self, user):
        return len([e for e in self.ends if e.user_id == user.id]) > 0

    def ended_for_all_users(self):
        users = list(set([a.user for a in self.acknowledged_activities]))
        for u in users:
            if not self.ended_for(u):
                return False
        return True

    def is_holiday(self):
        return (
            len([a for a in self.activities if a.type == ActivityType.OFF]) > 0
        )

    def is_empty(self):
        return len(self.activities) == 0

    def is_deleted(self):
        return all(activity.is_dismissed for activity in self.activities)

    def deleted_at(self):
        dismissed_times = [a.dismissed_at for a in self.activities]
        if len(dismissed_times) < len(self.activities):
            return None
        return max_or_none(*dismissed_times)
