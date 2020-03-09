from enum import Enum
from flask_jwt_extended import current_user

from app import db
from app.models.event import EventBaseModel, Revisable, DismissType
from app.models.utils import enum_column


class InputableActivityTypes(str, Enum):
    DRIVE = "drive"
    WORK = "work"
    BREAK = "break"
    REST = "rest"


ActivityTypes = Enum(
    "ActivityTypes",
    dict(
        SUPPORT="support",
        **{
            activity.name: activity.value
            for activity in InputableActivityTypes
        },
    ),
    type=str,
)


ActivityDismissType = Enum(
    "ActivityDismissType",
    dict(
        NO_ACTIVITY_SWITCH="no_activity_switch",
        **{
            dismiss_type.name: dismiss_type.value
            for dismiss_type in DismissType
        },
    ),
)


class Activity(EventBaseModel, Revisable):
    backref_base_name = "activities"

    type = enum_column(ActivityTypes, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)

    vehicle_registration_number = db.Column(db.String(255))
    mission = db.Column(db.String(255))

    team = db.Column(db.ARRAY(db.Integer), nullable=True)

    driver_idx = db.Column(db.Integer, nullable=True, default=None)
    is_driver_switch = db.Column(db.Boolean, nullable=True, default=None)

    dismiss_type = enum_column(ActivityDismissType, nullable=True)

    __table_args__ = (
        db.CheckConstraint(
            "(event_time >= start_time)",
            name="activity_start_time_before_event_time",
        ),
    )

    # TODO : add (maybe)
    # - validator
    # - version (each version represents a set of changes to the day activities)
    # OR revises (indicates which prior activity the current one revises)

    def to_dict(self):
        base_dict = super().to_dict()
        return dict(**base_dict, type=self.type, start_time=self.start_time)

    def __repr__(self):
        return f"<Activity [{self.id}] : {self.type.value}>"

    @property
    def is_acknowledged(self):
        return not self.is_dismissed and not self.is_revised

    @property
    def previous_and_next_acknowledged_activities(self):
        previous_activity = None
        for activity in self.user.acknowledged_activities:
            if activity.start_time > self.start_time:
                return previous_activity, activity
            if activity != self:
                previous_activity = activity
        return previous_activity, None

    @property
    def previous_acknowledged_activity(self):
        return self.previous_and_next_acknowledged_activities[0]

    @property
    def next_acknowledged_activity(self):
        return self.previous_and_next_acknowledged_activities[1]

    @property
    def is_duplicate(self):
        return (
            self.is_driver_switch
            or self.dismiss_type == ActivityDismissType.NO_ACTIVITY_SWITCH
        )

    def update_or_revise(self, revision_time, **updated_props):
        from app.domain.log_activities import log_activity

        if self.is_revised or self.is_dismissed:
            raise ValueError(
                f"You can't revise the already revised or dismissed {self}"
            )
        if not self.id:
            for prop, value in updated_props.items():
                setattr(self, prop, value)
            db.session.add(self)
            return self
        dict_ = dict(
            type=self.type,
            event_time=revision_time,
            start_time=self.start_time,
            user=self.user,
            submitter=current_user,
            vehicle_registration_number=self.vehicle_registration_number,
            mission=self.mission,
            team=self.team,
            driver_idx=self.driver_idx,
        )
        dict_.update(updated_props)
        revision = log_activity(**dict_)
        self.set_revision(revision, revision_time)
        db.session.add(revision)
        return revision
