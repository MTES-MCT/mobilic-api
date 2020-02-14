from enum import Enum
from app import db
from app.models.event import EventBaseValidationStatus, EventBaseModel
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


ActivityValidationStatus = Enum(
    "ActivityValidationStatus",
    dict(
        CONFLICTING_WITH_HISTORY="conflicting_with_history",
        NO_ACTIVITY_SWITCH="no_activity_switch",
        **{
            event_validation_status.name: event_validation_status.value
            for event_validation_status in EventBaseValidationStatus
        },
    ),
    type=str,
)


class Activity(EventBaseModel):
    backref_base_name = "activities"

    type = enum_column(ActivityTypes, nullable=False)

    vehicle_registration_number = db.Column(db.String(255))
    mission = db.Column(db.String(255))

    validation_status = enum_column(ActivityValidationStatus, nullable=False)

    team = db.Column(db.ARRAY(db.Integer), nullable=True)

    # TODO : add (maybe)
    # - validator
    # - version (each version represents a set of changes to the day activities)
    # OR revises (indicates which prior activity the current one revises)

    def to_dict(self):
        base_dict = super().to_dict()
        return dict(**base_dict, type=self.type,)
