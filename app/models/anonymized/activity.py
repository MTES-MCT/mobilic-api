from .base import AnonymizedModel
from sqlalchemy import Column, Integer, String, DateTime


class ActivityAnonymized(AnonymizedModel):
    __tablename__ = "activity_anonymized"

    id = Column(Integer, primary_key=True)
    type = Column(String(8), nullable=True)
    user_id = Column(Integer, nullable=True)
    submitter_id = Column(Integer, nullable=True)
    mission_id = Column(Integer, nullable=True)
    dismiss_author_id = Column(Integer, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    creation_time = Column(DateTime, nullable=True)
    reception_time = Column(DateTime, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    last_update_time = Column(DateTime, nullable=True)
    last_submitter_id = Column(Integer, nullable=True)

    @classmethod
    def anonymize(cls, activity):
        anonymized = cls()
        anonymized.id = cls.get_new_id("activity", activity.id)
        anonymized.type = activity.type
        anonymized.user_id = cls.get_new_id("user", activity.user_id)
        anonymized.submitter_id = cls.get_new_id("user", activity.submitter_id)
        anonymized.mission_id = cls.get_new_id("mission", activity.mission_id)
        anonymized.dismiss_author_id = cls.get_new_id(
            "user", activity.dismiss_author_id
        )
        anonymized.dismissed_at = cls.truncate_to_month(activity.dismissed_at)
        anonymized.creation_time = cls.truncate_to_month(
            activity.creation_time
        )
        anonymized.reception_time = cls.truncate_to_month(
            activity.reception_time
        )
        anonymized.start_time = cls.truncate_to_month(activity.start_time)
        anonymized.end_time = cls.truncate_to_month(activity.end_time)
        anonymized.last_update_time = cls.truncate_to_month(
            activity.last_update_time
        )
        anonymized.last_submitter_id = cls.get_new_id(
            "user", activity.last_submitter_id
        )
        return anonymized
