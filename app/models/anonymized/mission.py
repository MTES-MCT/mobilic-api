from .base import AnonymizedModel
from sqlalchemy import Column, Integer, DateTime


class MissionAnonymized(AnonymizedModel):
    __tablename__ = "mission_anonymized"

    id = Column(Integer, primary_key=True)
    submitter_id = Column(Integer, nullable=True)
    company_id = Column(Integer, nullable=True)
    creation_time = Column(DateTime, nullable=True)
    reception_time = Column(DateTime, nullable=True)

    @classmethod
    def anonymize(cls, mission):
        anonymized = cls()
        anonymized.id = cls.get_new_id("mission", mission.id)
        anonymized.submitter_id = cls.get_new_id("user", mission.submitter_id)
        anonymized.company_id = cls.get_new_id("company", mission.company_id)
        anonymized.creation_time = cls.truncate_to_month(mission.creation_time)
        anonymized.reception_time = cls.truncate_to_month(
            mission.reception_time
        )
        return anonymized
