from app import db
from .base import AnonymizedModel


class AnonControllerUser(AnonymizedModel):
    __tablename__ = "anon_controller_user"

    id = db.Column(db.Integer, primary_key=True)
    creation_time = db.Column(db.DateTime, nullable=False)

    @classmethod
    def anonymize(cls, controller):
        new_id = cls.get_new_id("controller_user", controller.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.creation_time = cls.truncate_to_month(
            controller.creation_time
        )
        return anonymized
