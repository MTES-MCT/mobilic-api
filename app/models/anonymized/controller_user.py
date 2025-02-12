from app import db
from .base import AnonymizedModel


class ControllerUserAnonymized(AnonymizedModel):
    __tablename__ = "anon_controller_user"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)

    @classmethod
    def anonymize(cls, controller):
        anonymized = cls()
        anonymized.id = cls.get_new_id("controller_user", controller.id)
        anonymized.creation_time = cls.truncate_to_month(
            controller.creation_time
        )
        return anonymized
