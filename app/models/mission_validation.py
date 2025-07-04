from enum import Enum

from sqlalchemy.orm import backref
from sqlalchemy.ext.declarative import declared_attr
import graphene

from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.event import UserEventBaseModel
from app.models.mixins.user_resolver import ResolveUser
from app.models.utils import enum_column


class OverValidationJustification(str, Enum):
    PERSONAL = "personal"
    PROFESSIONAL = "professional"
    TIME_OFF = "time_off"
    __description__ = """
Enumération des valeurs suivantes.
- "personal" : Raisons personnelles
- "professional" : Raisons professionnelles
- "time_off" : Congé
"""


class MissionValidation(UserEventBaseModel):
    backref_base_name = "mission_validations"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("validations"))
    is_admin = db.Column(db.Boolean, nullable=False)
    is_auto = db.Column(db.Boolean, nullable=False, default=False)

    justification = enum_column(OverValidationJustification, nullable=True)

    @declared_attr
    def user_id(cls):
        return db.Column(
            db.Integer, db.ForeignKey("user.id"), index=True, nullable=True
        )

    @declared_attr
    def submitter_id(cls):
        return db.Column(
            db.Integer, db.ForeignKey("user.id"), index=True, nullable=True
        )

    __table_args__ = (
        db.CheckConstraint(
            "(is_admin OR (user_id = submitter_id))",
            name="non_admin_can_only_validate_for_self",
        ),
        db.Constraint(
            name="only_one_validation_per_submitter_mission_and_user"
        ),
    )


class MissionValidationOutput(BaseSQLAlchemyObjectType, ResolveUser):
    class Meta:
        model = MissionValidation
        only_fields = (
            "id",
            "reception_time",
            "mission_id",
            "mission",
            "is_admin",
            "is_auto",
            "submitter_id",
            "submitter",
            "user_id",
            "user",
            "justification",
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
        required=False,
        description="Identifiant de la personne qui a effectué la validation",
    )
    user_id = graphene.Field(
        graphene.Int,
        description="Identifiant de la personne concernée par la validation, si il s'agit d'une validation restreinte aux enregistrements pour cette personne.",
    )
    is_admin = graphene.Field(
        graphene.Boolean,
        required=True,
        description="Indique si la validation provient d'un travailleur mobile ou d'un gestionnaire.",
    )
