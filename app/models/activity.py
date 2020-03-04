from enum import Enum
from app import db
from app.models.event import (
    EventBaseContext,
    EventBaseModel,
    Cancellable,
    Revisable,
)
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


ActivityContext = Enum(
    "ActivityContext",
    dict(
        CONFLICTING_WITH_HISTORY="conflicting_with_history",
        NO_ACTIVITY_SWITCH="no_activity_switch",
        DRIVER_SWITCH="driver_switch",
        **{
            event_context.name: event_context.value
            for event_context in EventBaseContext
        },
    ),
    type=str,
)


class Activity(EventBaseModel, Cancellable, Revisable):
    backref_base_name = "activities"

    type = enum_column(ActivityTypes, nullable=False)

    vehicle_registration_number = db.Column(db.String(255))
    mission = db.Column(db.String(255))

    context = enum_column(ActivityContext, nullable=True)

    team = db.Column(db.ARRAY(db.Integer), nullable=True)

    driver_idx = db.Column(db.Integer, nullable=True, default=None)

    # TODO : add (maybe)
    # - validator
    # - version (each version represents a set of changes to the day activities)
    # OR revises (indicates which prior activity the current one revises)

    def to_dict(self):
        base_dict = super().to_dict()
        return dict(**base_dict, type=self.type,)

    def __repr__(self):
        return f"<Activity [{self.id}] : {self.type.value}>"

    @property
    def is_acknowledged(self):
        return (
            self.context
            in [
                None,
                ActivityContext.NO_ACTIVITY_SWITCH,
                ActivityContext.DRIVER_SWITCH,
            ]
            and not self.is_cancelled
            and not self.is_revised
        )

    @property
    def is_duplicate(self):
        return self.context in [
            ActivityContext.NO_ACTIVITY_SWITCH,
            ActivityContext.DRIVER_SWITCH,
        ]

    @property
    def is_driver_switch(self):
        return self.context == ActivityContext.DRIVER_SWITCH
