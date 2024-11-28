from app import db
from app.models.expenditure import Expenditure


class ExpenditureAnonymized(Expenditure):
    backref_base_name = "expenditure_anonymized"
    __mapper_args__ = {"concrete": True}

    id = db.Column(db.Integer, primary_key=True)
    mission_d = db.Column(db.Integer, nullable=True)
    type = db.Column(db.String(10), nullable=True)
    user_id = db.Column(db.Integer, nullable=True)
    submitter_id = db.Column(db.Integer, nullable=True)
    dismiss_author_id = db.Column(db.Integer, nullable=True)
    creation_time = db.Column(db.DateTime, nullable=True)
    reception_time = db.Column(db.DateTime, nullable=True)
    dismissed_at = db.Column(db.DateTime, nullable=True)
    spending__date = db.Column(db.DateTime, nullable=True)
    dismiss_context = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<ExpenditureAnonymized(id={self.id}, mission_id={self.mission_id}, creation_time={self.creation_time})>"
