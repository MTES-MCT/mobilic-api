from enum import Enum
from app.models.base import BaseModel
from app import db
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


class ActivityValidationStatus(str, Enum):
    UNAUTHORIZED_SUBMITTER = "unauthorized_submitter"
    VALIDATED = "validated"
    PENDING = "pending"
    REJECTED = "rejected"


class Activity(BaseModel):
    type = enum_column(ActivityTypes, nullable=False)
    event_time = db.Column(db.DateTime, nullable=False)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=True, nullable=False
    )
    user = db.relationship("User", backref="activities")

    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref="activities")

    submitter_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=True, nullable=False
    )
    submitter = db.relationship("User", backref="submitted_activities")

    validated = enum_column(ActivityValidationStatus, nullable=False)

    # TODO : add (maybe)
    # - validator
    # - version (each version represents a set of changes to the day activities)
    # OR revises (indicates which prior activity the current one revises)
