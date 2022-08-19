import enum

import graphene
from sqlalchemy import Enum

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.graphene_types import BaseSQLAlchemyObjectType, TimeStamp
from app.models.base import BaseModel, RandomNineIntId


class ControlType(enum.Enum):
    mobilic = "Mobilic"
    lic_papier = "LIC papier"
    sans_lic = "Sans LIC"


class ControllerControl(BaseModel, RandomNineIntId):
    qr_code_generation_time = db.Column(DateTimeStoredAsUTC, nullable=False)

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
    company_name = db.Column(db.String(255), nullable=True)
    vehicule_registration_number = db.Column(db.TEXT, nullable=True)

    @staticmethod
    def get_or_create_mobilic_control(
        controller_id, user_id, qr_code_generation_time
    ):
        existing_control = ControllerControl.query.filter(
            ControllerControl.controller_id == controller_id,
            ControllerControl.user_id == user_id,
            ControllerControl.qr_code_generation_time
            == qr_code_generation_time,
        ).one_or_none()
        if existing_control:
            return existing_control
        else:
            new_control = ControllerControl(
                qr_code_generation_time=qr_code_generation_time,
                user_id=user_id,
                control_type=ControlType.mobilic,
                controller_id=controller_id,
            )
            db.session.add(new_control)
            db.session.commit()
            return new_control
