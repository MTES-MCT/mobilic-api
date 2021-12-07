from sqlalchemy.orm import backref
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timedelta

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.event import EventBaseModel


class Period:
    start_time = db.Column(DateTimeStoredAsUTC, nullable=False)
    end_time = db.Column(DateTimeStoredAsUTC, nullable=True)

    @db.validates("start_time", "end_time")
    def validates_start_time(self, key, start_time):
        try:
            return start_time.replace(second=0, microsecond=0)
        except:
            return None

    @property
    def duration(self):
        return (self.end_time or datetime.now()) - self.start_time

    # Duration of the activity period that is overlapping with the period given by start_time and end_time
    # This is mostly used for activities spanning several days, to split its duration among the different days
    def duration_over(self, start_time, end_time):
        if start_time and self.end_time and self.end_time <= start_time:
            return timedelta(0)

        if end_time and self.start_time >= end_time:
            return timedelta(0)

        self_end_time_or_now = self.end_time or datetime.now()

        return (
            min(self_end_time_or_now, end_time)
            if end_time
            else self_end_time_or_now
        ) - (
            max(self.start_time, start_time) if start_time else self.start_time
        )

    @property
    def type(self):
        raise NotImplementedError()


class ActivityVersion(EventBaseModel, Period):
    backref_base_name = "activity_versions"

    activity_id = db.Column(
        db.Integer, db.ForeignKey("activity.id"), index=True, nullable=False
    )
    activity = db.relationship("Activity", backref=backref("versions"))

    version_number = db.Column(db.Integer, nullable=False)
    context = db.Column(JSONB(none_as_null=True), nullable=True)

    @property
    def type(self):
        return self.activity.type

    @property
    def previous_version(self):
        previous_versions = sorted(
            [
                v
                for v in self.activity.versions
                if v.version_number < self.version_number
            ],
            key=lambda v: v.version_number,
        )
        return previous_versions[-1] if previous_versions else None

    __table_args__ = (
        db.UniqueConstraint(
            "version_number",
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
