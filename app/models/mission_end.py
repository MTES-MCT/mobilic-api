from sqlalchemy.orm import backref

from app import db
from app.models.event import UserEventBaseModel


class MissionEnd(UserEventBaseModel):
    backref_base_name = "mission_ends"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("ends"))

    __table_args__ = (
        db.UniqueConstraint(
            "mission_id", "user_id", name="user_can_only_end_mission_once"
        ),
    )
