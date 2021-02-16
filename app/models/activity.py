from enum import Enum
import graphene
from datetime import datetime
from graphene.types.generic import GenericScalar

from app.helpers.authentication import current_user
from sqlalchemy.orm import backref

from app import db, app
from app.helpers.errors import ResourceAlreadyDismissedError
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
    TimeStamp,
)
from app.models.event import UserEventBaseModel, Dismissable
from app.models.activity_version import ActivityVersion, Period
from app.models.utils import enum_column


def activity_versions_at(activities, at_time):
    versions = [a.version_at(at_time) for a in activities]
    return sorted(
        [v for v in versions if v],
        key=lambda v: (v.start_time, v.end_time is None, v.reception_time,),
    )


class ActivityType(str, Enum):
    DRIVE = "drive"
    WORK = "work"
    SUPPORT = "support"
    __description__ = """
Enumération des valeurs suivantes.
- "drive" : conduite du véhicule
- "work" : travail sans déplacement du véhicule
- "support" : accompagnement ou disponibilité
"""


class Activity(UserEventBaseModel, Dismissable, Period):
    backref_base_name = "activities"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("activities"))

    type = enum_column(ActivityType, nullable=False)

    last_update_time = db.Column(db.DateTime, nullable=False)

    editable_fields = {"start_time", "end_time"}

    __table_args__ = (
        db.Constraint(name="no_overlapping_acknowledged_activities"),
        db.Constraint(name="activity_start_time_before_end_time"),
        db.Constraint(name="activity_start_time_before_update_time"),
        db.Constraint(name="activity_end_time_before_update_time"),
        db.Constraint(name="no_successive_activities_with_same_type"),
    )

    # TODO : add (maybe)
    # - validator
    # - version (each version represents a set of changes to the day activities)
    # OR revises (indicates which prior activity the current one revises)

    def __repr__(self):
        return f"<Activity [{self.id}] : {self.type.value}>"

    def latest_version_number(self):
        return (
            max([r.version for r in self.revisions])
            if self.revisions
            else None
        )

    def version_at(self, at_time):
        if self.reception_time > at_time:
            return None
        if self.dismissed_at and self.dismissed_at <= at_time:
            return None
        return max(
            [r for r in self.revisions if r.reception_time <= at_time],
            key=lambda r: r.version,
        )

    def revise(
        self,
        revision_time,
        revision_context=None,
        bypass_check=False,
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
            app.logger.warning("No changes detected for the activity")
            return None

        with handle_activities_update(
            submitter=current_user,
            user=self.user,
            mission=self.mission,
            reception_time=revision_time,
            start_time=new["start_time"],
            end_time=new["end_time"],
            bypass_check=bypass_check,
        ):
            revision = ActivityVersion(
                activity=self,
                reception_time=revision_time,
                start_time=new["start_time"],
                end_time=new["end_time"],
                context=revision_context,
                version=(self.latest_version_number() or 0) + 1,
                submitter=current_user,
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
            bypass_check=True,
            reopen_mission_if_needed=False,
        ):
            super().dismiss(dismiss_time, context)
            self.last_update_time = self.dismissed_at


class ActivityOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Activity
        only_fields = (
            "id",
            "reception_time",
            "mission_id",
            "mission",
            "start_time",
            "end_time",
            "last_update_time",
            "type",
            "context",
            "user_id",
            "user",
            "submitter_id",
            "submitter",
        )
        description = (
            "Evènement de changement d'activité dans la journée de travail"
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant de l'activité"
    )
    mission_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la mission dans laquelle s'inscrit l'activité",
    )
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )
    start_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de début de l'activité",
    )
    end_time = graphene.Field(
        TimeStamp,
        required=False,
        description="Horodatage de fin de l'activité",
    )
    last_update_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de la dernière mise à jour de l'activité",
    )
    user_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant du travailleur mobile qui a effectué l'activité",
    )
    context = graphene.Field(
        GenericScalar, description="Données contextuelles libres"
    )
    submitter_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la personne qui a enregistré l'activité",
    )
    type = graphene_enum_type(ActivityType)(
        required=True, description="Nature de l'activité"
    )
