import enum

from sqlalchemy import Enum

from app import db
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.db import DateTimeStoredAsUTC
from app.models import User
from app.models.base import BaseModel, RandomNineIntId


class ControlType(enum.Enum):
    mobilic = "Mobilic"
    lic_papier = "LIC papier"
    sans_lic = "Sans LIC"


class ControllerControl(BaseModel, RandomNineIntId):
    qr_code_generation_time = db.Column(DateTimeStoredAsUTC, nullable=False)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    controller_id = db.Column(
        db.Integer,
        db.ForeignKey("controller_user.id"),
        nullable=False,
        index=True,
    )
    control_type = db.Column(Enum(ControlType))
    user = db.relationship("User")
    controller_user = db.relationship("ControllerUser")
    company_name = db.Column(db.String(255), nullable=True)
    vehicle_registration_number = db.Column(db.TEXT, nullable=True)
    nb_controlled_days = db.Column(db.Integer, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "controller_id",
            "user_id",
            "qr_code_generation_time",
            name="only_one_control_per_controller_user_date",
        ),
    )

    @staticmethod
    def get_or_create_mobilic_control(
        controller_id, user_id, qr_code_generation_time
    ):
        from app.data_access.control_data import compute_history_start_date

        existing_control = ControllerControl.query.filter(
            ControllerControl.controller_id == controller_id,
            ControllerControl.user_id == user_id,
            ControllerControl.qr_code_generation_time
            == qr_code_generation_time,
        ).one_or_none()
        if existing_control:
            return existing_control
        else:
            controlled_user = User.query.get(user_id)
            company_name = ""
            vehicle_registration_number = ""

            latest_activity_before = controlled_user.latest_activity_before(
                qr_code_generation_time
            )
            if latest_activity_before:
                latest_mission = latest_activity_before.mission
                is_latest_mission_ended = (
                    latest_mission.ended_for(controlled_user)
                    and latest_activity_before.end_time
                )
                if not is_latest_mission_ended:
                    company_name = (
                        latest_mission.company.legal_name
                        or latest_mission.company.usual_name
                    )
                    if latest_mission.vehicle:
                        vehicle_registration_number = (
                            latest_mission.vehicle.registration_number
                        )
            work_days = group_user_events_by_day_with_limit(
                user=controlled_user,
                from_date=compute_history_start_date(
                    qr_code_generation_time.date()
                ),
                until_date=qr_code_generation_time.date(),
                include_dismissed_or_empty_days=False,
            )[0]
            nb_controlled_days = len(work_days)
            new_control = ControllerControl(
                qr_code_generation_time=qr_code_generation_time,
                user_id=user_id,
                control_type=ControlType.mobilic,
                controller_id=controller_id,
                company_name=company_name,
                vehicle_registration_number=vehicle_registration_number,
                nb_controlled_days=nb_controlled_days,
            )
            db.session.add(new_control)
            db.session.commit()
            return new_control
