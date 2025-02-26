from app import db
from .base import AnonymizedModel


class AnonMission(AnonymizedModel):
    __tablename__ = "anon_mission"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    submitter_id = db.Column(db.Integer, nullable=False)
    company_id = db.Column(db.Integer, nullable=False)

    @classmethod
    def anonymize(cls, mission):
        anonymized = cls()
        anonymized.id = cls.get_new_id("mission", mission.id)
        anonymized.submitter_id = cls.get_new_id("user", mission.submitter_id)
        anonymized.company_id = cls.get_new_id("company", mission.company_id)
        anonymized.creation_time = cls.truncate_to_month(mission.creation_time)

        return anonymized
