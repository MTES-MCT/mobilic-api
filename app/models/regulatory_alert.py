from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.helpers.submitter_type import SubmitterType
from app.models.base import BaseModel
from app.models.utils import enum_column


class RegulatoryAlert(BaseModel):
    backref_base_name = "regulatory_alert"

    day = db.Column(db.Date, nullable=False)
    extra = db.Column(JSONB(none_as_null=True), nullable=True)
    submitter_type = enum_column(SubmitterType, nullable=False)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=False, nullable=False
    )
    user = db.relationship("User", backref="regulatory_alerts")

    regulation_check_id = db.Column(
        db.Integer,
        db.ForeignKey("regulation_check.id"),
        index=True,
        nullable=False,
    )
    regulation_check = db.relationship("RegulationCheck")

    business_id = db.Column(
        db.Integer,
        db.ForeignKey("business.id"),
        index=False,
        nullable=False,
    )
    business = db.relationship("Business")

    __table_args__ = (
        db.UniqueConstraint(
            "day",
            "user_id",
            "regulation_check_id",
            "submitter_type",
            name="only_one_entry_per_user_day_check_and_submitter_type",
        ),
    )

    def __repr__(self):
        return "<RegulatoryAlert [{}] : {}, {}, {}, {}, {}>".format(
            self.id,
            self.user,
            self.submitter_type,
            self.regulation_check,
            self.day,
            self.business,
        )
