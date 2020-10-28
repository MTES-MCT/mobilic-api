from sqlalchemy.orm import backref
from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.models.event import EventBaseModel


class ActivityVersion(EventBaseModel):
    backref_base_name = "activity_revisions"

    activity_id = db.Column(
        db.Integer, db.ForeignKey("activity.id"), index=True, nullable=False
    )
    activity = db.relationship("Activity", backref=backref("revisions"))

    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)

    version = db.Column(db.Integer, nullable=False)
    context = db.Column(JSONB(none_as_null=True), nullable=True)

    @db.validates("start_time", "end_time")
    def validates_start_time(self, key, start_time):
        try:
            return start_time.replace(second=0, microsecond=0)
        except:
            return None

    __table_args__ = (
        db.UniqueConstraint(
            "version",
            "activity_id",
            name="unique_version_among_same_activity_versions",
        ),
        db.Constraint(
            name="activity_version_start_time_before_reception_time"
        ),
        db.Constraint(name="activity_version_end_time_before_reception_time"),
        db.Constraint(name="activity_version_start_time_before_end_time"),
    )

    def __repr__(self):
        return f"<Revision [{self.id}] of {self.activity}>"
