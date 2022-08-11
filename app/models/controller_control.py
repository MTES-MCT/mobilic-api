import enum

import graphene
from sqlalchemy import Enum

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.graphene_types import TimeStamp, BaseSQLAlchemyObjectType
from app.models.base import BaseModel


class ControlType(enum.Enum):
    mobilic = "Mobilic"
    lic_papier = "LIC papier"
    sans_lic = "Sans LIC"


class ControllerControl(BaseModel):
    valid_from = db.Column(DateTimeStoredAsUTC, nullable=False)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    controller_id = db.Column(
        db.Integer,
        db.ForeignKey("controller_user.id"),
        nullable=False,
        index=True,
    )
    control_type = db.Column(Enum(ControlType))
    user = db.relationship("User")
    controller_user = db.relationship("ControllerUser")


class ControllerControlOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ControllerControl

    creation_time = graphene.Field(TimeStamp, required=True)
    creation_day = graphene.Field(graphene.Date, required=True)
    valid_until = graphene.Field(TimeStamp, required=True)

    history_start_day = graphene.Field(graphene.Date, required=True)
