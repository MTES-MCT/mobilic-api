from sqlalchemy.orm import backref

from app import db
from app.models.event import EventBaseModel


class MissionValidation(EventBaseModel):
    backref_base_name = "mission_validations"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("validations"))
