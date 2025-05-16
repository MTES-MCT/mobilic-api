from app import db
from .base import AnonymizedModel


class AnonControllerControl(AnonymizedModel):
    __tablename__ = "anon_controller_control"

    id = db.Column(db.Integer, primary_key=True)
    controller_id = db.Column(db.Integer, nullable=False)
    control_type = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    qr_code_generation_time = db.Column(db.DateTime, nullable=True)
    creation_time = db.Column(db.DateTime, nullable=False)
    control_bulletin_creation_time = db.Column(db.DateTime, nullable=True)
    control_bulletin_first_download_time = db.Column(
        db.DateTime, nullable=True
    )
    observed_infractions = db.Column(db.JSON, nullable=True)
    reported_infractions_last_update_time = db.Column(
        db.DateTime, nullable=True
    )
    reported_infractions_first_update_time = db.Column(
        db.DateTime, nullable=True
    )

    @classmethod
    def anonymize(cls, control):
        new_id = cls.get_new_id("controller_control", control.id)

        existing = cls.check_existing_record(new_id)
        if existing:
            return existing

        anonymized = cls()
        anonymized.id = new_id
        anonymized.controller_id = cls.get_new_id(
            "user", control.controller_id
        )
        anonymized.control_type = control.control_type.value
        anonymized.user_id = cls.get_new_id("user", control.user_id)
        anonymized.qr_code_generation_time = cls.truncate_to_month(
            control.qr_code_generation_time
        )
        anonymized.creation_time = cls.truncate_to_month(control.creation_time)
        anonymized.control_bulletin_creation_time = cls.truncate_to_month(
            control.control_bulletin_creation_time
        )
        if control.control_bulletin_first_download_time:
            anon_creation_time = cls.truncate_to_month(
                control.control_bulletin_creation_time
            )
            time_diff = (
                control.control_bulletin_first_download_time
                - control.control_bulletin_creation_time
            )
            anonymized.control_bulletin_first_download_time = (
                anon_creation_time + time_diff
            )
        else:
            control.control_bulletin_first_download_time = None
        anonymized.observed_infractions = control.observed_infractions
        if control.reported_infractions_last_update_time:
            anon_creation_time = cls.truncate_to_month(
                control.control_bulletin_creation_time
            )
            time_diff = (
                control.reported_infractions_last_update_time
                - control.control_bulletin_creation_time
            )
            anonymized.reported_infractions_last_update_time = (
                anon_creation_time + time_diff
            )
        else:
            anonymized.reported_infractions_last_update_time = None
        if control.reported_infractions_first_update_time:
            anon_creation_time = cls.truncate_to_month(
                control.control_bulletin_creation_time
            )
            time_diff = (
                control.reported_infractions_first_update_time
                - control.control_bulletin_creation_time
            )
            anonymized.reported_infractions_first_update_time = (
                anon_creation_time + time_diff
            )
        else:
            anonymized.reported_infractions_first_update_time = None
        return anonymized
