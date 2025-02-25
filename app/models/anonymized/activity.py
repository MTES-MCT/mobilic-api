from app import db
from .base import AnonymizedModel


class AnonActivity(AnonymizedModel):
    __tablename__ = "anon_activity"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(8), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    submitter_id = db.Column(db.Integer, nullable=False)
    mission_id = db.Column(db.Integer, nullable=False)
    creation_time = db.Column(db.DateTime, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    last_update_time = db.Column(db.DateTime, nullable=False)

    @classmethod
    def anonymize(cls, activity):
        anonymized = cls()
        anonymized.id = cls.get_new_id("activity", activity.id)
        anonymized.user_id = cls.get_new_id("user", activity.user_id)
        anonymized.submitter_id = cls.get_new_id("user", activity.submitter_id)
        anonymized.mission_id = cls.get_new_id("mission", activity.mission_id)
        anonymized.type = activity.type
        anonymized.creation_time = cls.truncate_to_month(
            activity.creation_time
        )
        anonymized.start_time = cls.truncate_to_month(activity.start_time)
        anonymized.last_update_time = cls.truncate_to_month(
            activity.last_update_time
        )
        # keep the difference for stats
        if activity.end_time and activity.start_time:
            time_diff = activity.end_time - activity.start_time
            anonymized.end_time = anonymized.start_time + time_diff
        else:
            anonymized.end_time = None

        return anonymized
