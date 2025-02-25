from app import db
from .base import AnonymizedModel


class AnonRegulationComputation(AnonymizedModel):
    __tablename__ = "anon_regulation_computation"
    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    day = db.Column(db.Date, nullable=False)
    submitter_type = db.Column(db.String(length=50), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)

    @classmethod
    def anonymize(cls, computation):
        anonymized = cls()
        anonymized.id = cls.get_new_id(
            "regulation_computation", computation.id
        )
        anonymized.creation_time = cls.truncate_to_month(
            computation.creation_time
        )
        anonymized.day = computation.day
        anonymized.submitter_type = computation.submitter_type
        anonymized.user_id = cls.get_new_id("user", computation.user_id)
        return anonymized
