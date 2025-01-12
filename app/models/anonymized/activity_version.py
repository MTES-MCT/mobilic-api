from .base import AnonymizedModel
from sqlalchemy import Column, Integer, DateTime, JSON


class ActivityVersionAnonymized(AnonymizedModel):
    __tablename__ = "activity_version_anonymized"

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, nullable=True)
    version_number = Column(Integer, nullable=True)
    submitter_id = Column(Integer, nullable=True)
    creation_time = Column(DateTime, nullable=True)
    reception_time = Column(DateTime, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    context = Column(JSON, nullable=True)

    @classmethod
    def anonymize(cls, version):
        anonymized = cls()
        anonymized.id = cls.get_new_id("activity_version", version.id)
        anonymized.activity_id = cls.get_new_id(
            "activity", version.activity_id
        )
        anonymized.version_number = version.version_number
        anonymized.submitter_id = cls.get_new_id("user", version.submitter_id)
        anonymized.creation_time = cls.truncate_to_month(version.creation_time)
        anonymized.reception_time = cls.truncate_to_month(
            version.reception_time
        )
        anonymized.start_time = cls.truncate_to_month(version.start_time)
        anonymized.end_time = cls.truncate_to_month(version.end_time)
        anonymized.context = None
        return anonymized
