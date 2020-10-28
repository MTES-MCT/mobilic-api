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
from app.models.activity_version import ActivityVersion
from app.models.utils import enum_column


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


class Activity(UserEventBaseModel, Dismissable):
    backref_base_name = "activities"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("activities"))

    type = enum_column(ActivityType, nullable=False)

    last_update_time = db.Column(db.DateTime, nullable=False)

    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)

    editable_fields = {"start_time", "end_time"}

    __table_args__ = (
        db.Constraint(name="no_overlapping_acknowledged_activities"),
        db.Constraint(name="activity_start_time_before_end_time"),
        db.Constraint(name="activity_start_time_before_update_time"),
        db.Constraint(name="activity_end_time_before_update_time"),
        db.Constraint(name="no_sucessive_activities_with_same_type"),
    )

    # TODO : add (maybe)
    # - validator
    # - version (each version represents a set of changes to the day activities)
    # OR revises (indicates which prior activity the current one revises)

    @db.validates("start_time", "end_time")
    def validates_start_time(self, key, time):
        try:
            return time.replace(second=0, microsecond=0)
        except:
            return None

    def __repr__(self):
        return f"<Activity [{self.id}] : {self.type.value}>"

    def latest_revision_version(self):
        return (
            max([r.version for r in self.revisions])
            if self.revisions
            else None
        )

    @property
    def duration(self):
        return (self.end_time or datetime.now()) - self.start_time

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
                version=(self.latest_revision_version() or 0) + 1,
                submitter=current_user,
            )
            db.session.add(revision)

            for field, value in updated_props.items():
                setattr(self, field, value)

            self.last_update_time = revision_time
            db.session.add(self)

            return revision

    def dismiss(self, dismiss_time=None, context=None):
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
