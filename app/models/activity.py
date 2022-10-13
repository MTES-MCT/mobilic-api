from enum import Enum
from datetime import datetime

from sqlalchemy import event

from app.helpers.authentication import current_user
from sqlalchemy.orm import backref

from app import db, app
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.errors import ResourceAlreadyDismissedError
from app.helpers.frozen_version_utils import filter_out_future_events
from app.models.event import UserEventBaseModel, Dismissable
from app.models.activity_version import ActivityVersion, Period
from app.models.utils import enum_column


def activity_versions_at(activities, at_time):
    versions = [a.version_at(at_time) for a in activities]
    return sorted(
        [v for v in versions if v],
        key=lambda v: (
            v.start_time,
            v.end_time is None,
            v.reception_time,
        ),
    )


def is_activity_considered_work(activity_type):
    return activity_type in [
        item for item in ActivityType if item != ActivityType.TRANSFER
    ]


class ActivityType(str, Enum):
    DRIVE = "drive"
    WORK = "work"
    SUPPORT = "support"
    TRANSFER = "transfer"
    __description__ = """
Enumération des valeurs suivantes.
- "drive" : conduite du véhicule
- "work" : travail sans déplacement du véhicule
- "support" : accompagnement ou disponibilité
- "transfer": liaison d'un point à un autre
"""


class Activity(UserEventBaseModel, Dismissable, Period):
    backref_base_name = "activities"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("activities"))

    type = enum_column(ActivityType, nullable=False)

    last_update_time = db.Column(DateTimeStoredAsUTC, nullable=False)

    last_submitter_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )

    editable_fields = {"start_time", "end_time"}

    __table_args__ = (
        db.Constraint(name="no_overlapping_acknowledged_activities"),
        db.Constraint(name="activity_start_time_before_end_time"),
        db.Constraint(name="activity_start_time_before_update_time"),
        db.Constraint(name="activity_end_time_before_update_time"),
        db.Constraint(name="no_successive_activities_with_same_type"),
        db.Constraint(name="activity_last_submitter_id_fkey"),
    )

    def __repr__(self):
        return f"<Activity [{self.id}] : {self.type.value}>"

    def latest_version_number(self):
        return (
            max([r.version_number for r in self.versions])
            if self.versions
            else None
        )

    def version_at(self, at_time):
        if self.reception_time > at_time:
            return None
        if self.dismissed_at and self.dismissed_at <= at_time:
            return None
        versions_before = [
            r for r in self.versions if r.reception_time <= at_time
        ]
        if versions_before:
            return max(
                versions_before,
                default=None,
                key=lambda r: r.version_number,
            )
        else:
            return min(
                [r for r in self.versions],
                default=None,
                key=lambda r: r.version_number,
            )

    def freeze_activity_at(self, at_time):
        frozen_version = self.version_at(at_time)
        if frozen_version:
            self.start_time = frozen_version.start_time
            if frozen_version.end_time:
                self.end_time = frozen_version.end_time
            else:
                self.end_time = at_time
            return self
        else:
            return None

    def latest_modification_time_by(self, user):
        if self.dismiss_author_id == user.id:
            return self.dismissed_at
        user_revision_times = [
            r.reception_time
            for r in self.versions
            if r.submitter_id == user.id
        ]
        return max(user_revision_times) if user_revision_times else None

    def revise(
        self,
        revision_time,
        revision_context=None,
        bypass_overlap_check=False,
        bypass_auth_check=False,
        creation_time=None,
        **updated_props,
    ):
        from app.domain.log_activities import handle_activities_update

        if self.is_dismissed:
            raise ResourceAlreadyDismissedError("Activity already dismissed")

        if not set(updated_props.keys()) <= Activity.editable_fields:
            raise ValueError("Bad arguments to revise method")

        new = {
            field: updated_props.get(field, getattr(self, field))
            for field in Activity.editable_fields
        }
        old = {
            field: getattr(self, field) for field in Activity.editable_fields
        }

        if new == old:
            app.logger.warning(
                "No changes detected for the activity",
                extra={"to_secondary_slack_channel": True},
            )
            return None

        with handle_activities_update(
            submitter=current_user,
            user=self.user,
            mission=self.mission,
            reception_time=revision_time,
            start_time=new["start_time"],
            end_time=new["end_time"],
            bypass_overlap_check=bypass_overlap_check,
            bypass_auth_check=bypass_auth_check,
        ):
            revision = ActivityVersion(
                activity=self,
                reception_time=revision_time,
                start_time=new["start_time"],
                end_time=new["end_time"],
                context=revision_context,
                version_number=(self.latest_version_number() or 0) + 1,
                submitter=current_user,
                creation_time=creation_time,
            )
            db.session.add(revision)

            for field, value in updated_props.items():
                setattr(self, field, value)

            self.last_update_time = revision_time
            db.session.add(self)

            return revision

    def dismiss(self, dismiss_time=None, context=None):
        from app.domain.log_activities import handle_activities_update

        if not dismiss_time:
            dismiss_time = datetime.now()

        with handle_activities_update(
            submitter=current_user,
            user=self.user,
            mission=self.mission,
            reception_time=dismiss_time,
            start_time=self.start_time,
            end_time=None,
            bypass_overlap_check=True,
            reopen_mission_if_needed=False,
        ):
            super().dismiss(dismiss_time, context)
            self.last_update_time = self.dismissed_at

    def retrieve_all_versions(self, max_reception_time=None):
        if max_reception_time:
            return filter_out_future_events(self.versions, max_reception_time)
        else:
            return self.versions


@event.listens_for(Activity, "after_insert")
@event.listens_for(Activity, "after_update")
def set_last_submitter_id(mapper, connect, target):
    target.last_submitter_id = current_user.id
