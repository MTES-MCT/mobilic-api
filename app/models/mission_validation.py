from sqlalchemy.orm import backref
import graphene

from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.event import EventBaseModel


class MissionValidation(EventBaseModel):
    backref_base_name = "mission_validations"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("validations"))


class MissionValidationOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = MissionValidation
        only_fields = (
            "id",
            "reception_time",
            "mission_id",
            "mission",
            "submitter_id",
            "submitter",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant de la validation"
    )
    mission_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la mission à laquelle se rattache la validation",
    )
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de validation des informations de la mission",
    )
    submitter_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la personne qui a effectué la validation",
    )
