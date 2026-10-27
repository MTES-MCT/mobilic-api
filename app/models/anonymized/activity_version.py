from app import db
from .base import AnonymizedModel


class AnonActivityVersion(AnonymizedModel):
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
        new_id = cls.get_new_id("activity_version", version.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.activity_id = cls.get_new_id(
            "activity", version.activity_id
        )
        anonymized.submitter_id = cls.get_new_id("user", version.submitter_id)
        anonymized.version_number = version.version_number
        anonymized.creation_time = cls.truncate_to_month(version.creation_time)
        anonymized.start_time = cls.truncate_to_month(version.start_time)
        anonymized.end_time = cls.bucket_end_time(
            anonymized.start_time, version.end_time
        )

        return anonymized
