import enum

import graphene
from sqlalchemy import Enum

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.graphene_types import TimeStamp, BaseSQLAlchemyObjectType
from app.models.base import BaseModel, RandomNineIntId


class ControlType(enum.Enum):
    mobilic = "Mobilic"
    lic_papier = "LIC papier"
    sans_lic = "Sans LIC"


class ControllerControl(BaseModel, RandomNineIntId):
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

    @staticmethod
    def get_or_create_mobilic_control(controller_id, user_id, valid_from):
        existing_controls = ControllerControl.query.filter(
            ControllerControl.controller_id == controller_id,
            ControllerControl.user_id == user_id,
            ControllerControl.valid_from == valid_from,
        ).all()
        if existing_controls:
            return existing_controls[0]
        else:
            new_control = ControllerControl(
                valid_from=valid_from,
                user_id=user_id,
                control_type=ControlType.mobilic,
                controller_id=controller_id,
            )
            db.session.add(new_control)
            db.session.commit()
            return new_control


class ControllerControlOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = ControllerControl

    creation_time = graphene.Field(TimeStamp, required=True)
    creation_day = graphene.Field(graphene.Date, required=True)
    valid_until = graphene.Field(TimeStamp, required=True)

    history_start_day = graphene.Field(graphene.Date, required=True)
