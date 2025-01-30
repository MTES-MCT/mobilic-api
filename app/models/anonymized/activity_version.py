from app import db
from .base import AnonymizedModel


class ActivityVersionAnonymized(AnonymizedModel):
    __tablename__ = "anon_activity_version"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    activity_id = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    version_number = db.Column(db.Integer, nullable=False)
    submitter_id = db.Column(db.Integer, nullable=False)

    @classmethod
    def anonymize(cls, version):
        anonymized = cls()
        anonymized.id = cls.get_new_id("activity_version", version.id)
        anonymized.activity_id = cls.get_new_id(
            "activity", version.activity_id
        )
        anonymized.submitter_id = cls.get_new_id("user", version.submitter_id)
        anonymized.version_number = version.version_number
        anonymized.creation_time = cls.truncate_to_month(version.creation_time)
        anonymized.start_time = cls.truncate_to_month(version.start_time)
        # keep the difference for stats
        if version.end_time and version.start_time:
            start_time_anon = cls.truncate_to_month(version.start_time)
            time_diff = version.end_time - version.start_time
            anonymized.end_time = start_time_anon + time_diff
        else:
            anonymized.end_time = None

        return anonymized
