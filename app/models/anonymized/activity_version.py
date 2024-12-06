from app import db
from app.models.activity_version import ActivityVersion


class ActivityVersionAnonymized(ActivityVersion):
    backref_base_name = "activity_version_anonymized"
    __mapper_args__ = {"concrete": True}

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, nullable=True)
    version_number = db.Column(db.Integer, nullable=True)
    submitter_id = db.Column(db.Integer, nullable=True)
    creation_time = db.Column(db.DateTime, nullable=True)
    reception_time = db.Column(db.DateTime, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    context = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<ActivityVersionAnonymized(id={self.id}, activity_id={self.activity_id}, version_number={self.version_number})>"
