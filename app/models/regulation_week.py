from enum import Enum
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.helpers.submitter_type import SubmitterType
from app.models.base import BaseModel
from app.models.utils import enum_column


class RegulationWeek(BaseModel):
    backref_base_name = "regulation_week"

    week = db.Column(db.Date, nullable=False)
    success = db.Column(db.Boolean, nullable=False)
    extra = db.Column(JSONB(none_as_null=True), nullable=True)
    submitter_type = enum_column(SubmitterType, nullable=False)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=False, nullable=False
    )
    user = db.relationship("User", backref="regulation_weeks")

    regulation_check_id = db.Column(
        db.Integer,
        db.ForeignKey("regulation_check.id"),
        index=True,
        nullable=False,
    )
    regulation_check = db.relationship("RegulationCheck")

    __table_args__ = (
        db.UniqueConstraint(
            "week",
            "user_id",
            "regulation_check_id",
            "submitter_type",
            name="only_one_entry_per_user_week_check_and_submitter_type",
        ),
    )
