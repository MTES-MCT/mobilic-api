from app import db
from app.models.mission import Mission


class MissionAnonymized(Mission):
    backref_base_name = "mission_anonymized"
    __mapper_args__ = {"concrete": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=True)
    submitter_id = db.Column(db.Integer, nullable=True)
    company_id = db.Column(db.Integer, nullable=True)
    vehicle_id = db.Column(db.Integer, nullable=True)
    creation_time = db.Column(db.DateTime, nullable=True)
    reception_time = db.Column(db.DateTime, nullable=True)
    context = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<MissionAnonymized(id={self.id}, name={self.name}, creation_time={self.creation_time})>"
