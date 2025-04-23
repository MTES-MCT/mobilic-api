from sqlalchemy import UniqueConstraint

from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel
from sqlalchemy.orm import backref

from app import db


class MissionAutoValidation(BaseModel):
    backref_base_name = "mission_auto_validations"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("auto_validations"))
    is_admin = db.Column(db.Boolean, nullable=False)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship(
        "User", backref=backref("auto_validations", lazy=True)
    )

    reception_time = db.Column(DateTimeStoredAsUTC, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "mission_id", "is_admin", name="uq_user_mission_admin"
        ),
    )
