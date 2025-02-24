from app import db
from .base import AnonymizedModel


class MissionEndAnonymized(AnonymizedModel):
    __tablename__ = "anon_mission_end"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    mission_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    submitter_id = db.Column(db.Integer, nullable=False)

    @classmethod
    def anonymize(cls, mission_end):
        anonymized = cls()
        anonymized.id = cls.get_new_id("mission_end", mission_end.id)
        anonymized.mission_id = cls.get_new_id(
            "mission", mission_end.mission_id
        )
        anonymized.user_id = cls.get_new_id("user", mission_end.user_id)
        anonymized.submitter_id = cls.get_new_id(
            "user", mission_end.submitter_id
        )
        anonymized.creation_time = cls.truncate_to_month(
            mission_end.creation_time
        )

        return anonymized
