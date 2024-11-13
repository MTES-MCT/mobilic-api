from app import db
from app.models.activity import Activity


class ActivityAnonymized(Activity):
    backref_base_name = "activity_anonymized"
    __mapper_args__ = {"concrete": True}

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(8), nullable=True)
    user_id = db.Column(db.Integer, nullable=True)
    submitter_id = db.Column(db.Integer, nullable=True)
    mission_id = db.Column(db.Integer, nullable=True)
    dismiss_author_id = db.Column(db.Integer, nullable=True)
    dismissed_at = db.Column(db.DateTime, nullable=True)
    creation_time = db.Column(db.DateTime, nullable=True)
    reception_time = db.Column(db.DateTime, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    last_update_time = db.Column(db.DateTime, nullable=True)
    last_submitter_id = db.Column(db.Integer, nullable=True)
    dismiss_context = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<ActivityAnonymized(id={self.id}, type={self.type}, creation_time={self.creation_time})>"
