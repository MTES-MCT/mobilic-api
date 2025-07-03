from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import backref

from app import db
from app.models.event import UserEventBaseModel


class MissionEnd(UserEventBaseModel):
    backref_base_name = "mission_ends"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("ends"))

    @declared_attr
    def submitter_id(cls):
        return db.Column(
            db.Integer, db.ForeignKey("user.id"), index=True, nullable=True
        )

    __table_args__ = (db.Constraint(name="user_can_only_end_mission_once"),)
