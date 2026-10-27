from app import db
from app.helpers.submitter_type import SubmitterType
from app.models.base import BaseModel
from app.models.utils import enum_column


class RegulationComputation(BaseModel):
    backref_base_name = "regulation_computation"

    day = db.Column(db.Date, nullable=False)
    submitter_type = enum_column(SubmitterType, nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=False, nullable=False
    )
    user = db.relationship("User", backref="regulation_computations")

    __table_args__ = (
        db.UniqueConstraint(
            "day",
            "user_id",
            "submitter_type",
            name="only_one_entry_per_user_day_and_submitter_type",
        ),
        db.Index(
            "ix_regulation_computation_user_submitter_day",
            "user_id",
            "submitter_type",
            "day",
        ),
    )

    def __repr__(self):
        return "<RegulationComputation [{}] : {}, {}, {}>".format(
            self.id,
            self.user,
            self.day,
            self.submitter_type,
        )
