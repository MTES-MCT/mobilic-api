from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum

from app import db
from app.models.event import EventBaseModel


def _max_or_none(*args):
    args_not_none = [a for a in args if a is not None]
    return max(args_not_none) if args_not_none else None


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

    def activities_for(self, user, include_dismissed_activities=False):
        all_activities_for_user = sorted(
            [a for a in self.activities if a.user_id == user.id],
            key=lambda a: a.start_time,
        )
        if not include_dismissed_activities:
            return [a for a in all_activities_for_user if not a.is_dismissed]
        return all_activities_for_user

    def current_activity_at_time_for_user(self, user, date_time):
        for activity in self.activities_for(user):
            if activity.start_time <= date_time and (
                not activity.end_time or activity.end_time > date_time
            ):
                return activity
        return None

    def expenditures_for(self, user):
        return [
            e for e in self.acknowledged_expenditures if e.user_id == user.id
        ]

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
    def latest_validations_per_user(self):
        latest_validations_by_user = {}
        for validation in self.validations:
            current_latest_val_for_user = latest_validations_by_user.get(
                validation.submitter_id
            )
            if (
                not current_latest_val_for_user
                or current_latest_val_for_user.reception_time
                < validation.reception_time
            ):
                latest_validations_by_user[
                    validation.submitter_id
                ] = validation

        return list(latest_validations_by_user.values())

    @property
    def start_location(self):
        from app.models.location_entry import LocationEntryType

        start_location_entry = [
            l
            for l in self.location_entries
            if l.type == LocationEntryType.MISSION_START_LOCATION
        ]
        return start_location_entry[0] if start_location_entry else None

    @property
    def end_location(self):
        from app.models.location_entry import LocationEntryType

        end_location_entry = [
            l
            for l in self.location_entries
            if l.type == LocationEntryType.MISSION_END_LOCATION
        ]
        return end_location_entry[0] if end_location_entry else None

    def validations_of(self, user):
        return [
            v
            for v in self.validations
            if v.submitter_id == user.id
            and (v.user_id is None or v.user_id == user.id)
        ]

    def latest_validation_time_of(self, user):
        user_validations = self.validations_of(user)
        return (
            max([u.reception_time for u in user_validations])
            if user_validations
            else None
        )

    @property
    def validated_by_admin(self):
        return any([v.is_admin and not v.user_id for v in self.validations])

    def validated_by_admin_for(self, user):
        return any(
            [
                v.is_admin and (not v.user_id or v.user_id == user.id)
                for v in self.validations
            ]
        )

    def modification_status_and_latest_action_time_for_user(self, user):
        latest_validation_time = self.latest_validation_time_of(user)
        all_user_activities = self.activities_for(
            user, include_dismissed_activities=True
        )
        if not all_user_activities:
            return UserMissionModificationStatus.NO_DATA_FOR_USER, None

        latest_user_activity_modification_time = _max_or_none(
            *[a.latest_modification_time_by(user) for a in all_user_activities]
        )
        latest_user_action_time = _max_or_none(
            latest_validation_time, latest_user_activity_modification_time
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

    def ended_for(self, user):
        return len([e for e in self.ends if e.user_id == user.id]) > 0
