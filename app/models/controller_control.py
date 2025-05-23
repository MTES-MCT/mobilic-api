import datetime
import enum
from datetime import date

from sqlalchemy import Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from app import db, app
from app.domain.controller_control import get_no_lic_observed_infractions
from app.domain.regulation_computations import (
    get_regulatory_alerts,
    get_regulatory_computations,
)
from app.domain.work_days import group_user_events_by_day_with_limit
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.submitter_type import SubmitterType
from app.models import User, RegulationCheck
from app.models.base import BaseModel, RandomNineIntId


class ControlType(enum.Enum):
    mobilic = "Mobilic"
    lic_papier = "LIC papier"
    sans_lic = "Pas de LIC"


def compute_history_start_date(history_end_date):
    return history_end_date - app.config["USER_CONTROL_HISTORY_DEPTH"]


class ControllerControl(BaseModel, RandomNineIntId):
    qr_code_generation_time = db.Column(DateTimeStoredAsUTC, nullable=True)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True, index=True
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
    user_first_name = db.Column(db.String(255), nullable=True)
    user_last_name = db.Column(db.String(255), nullable=True)
    vehicle_registration_number = db.Column(db.TEXT, nullable=True)
    is_day_page_filled = db.Column(db.Boolean, nullable=True)
    nb_controlled_days = db.Column(db.Integer, nullable=True)
    control_bulletin = db.Column(
        MutableDict.as_mutable(JSONB(none_as_null=True)), nullable=True
    )
    control_bulletin_creation_time = db.Column(
        DateTimeStoredAsUTC, nullable=True
    )
    control_bulletin_first_download_time = db.Column(
        DateTimeStoredAsUTC, nullable=True
    )
    note = db.Column(db.TEXT, nullable=True)
    observed_infractions = db.Column(JSONB(none_as_null=True), nullable=True)
    reported_infractions_first_update_time = db.Column(
        DateTimeStoredAsUTC, nullable=True
    )
    reported_infractions_last_update_time = db.Column(
        DateTimeStoredAsUTC, nullable=True
    )

    @property
    def history_end_date(self):
        return (
            self.qr_code_generation_time.date()
            if self.qr_code_generation_time
            else None
        )

    @property
    def history_start_date(self):
        return (
            compute_history_start_date(self.history_end_date)
            if self.history_end_date
            else None
        )

    @property
    def reference(self):
        today = date.today()
        return (
            f"{self.id}-{today.strftime('%Y')}-{self.controller_user.greco_id}"
        )

    @property
    def bdc_filename(self):
        return f"{self.company_name}-{self.creation_time.strftime('%d%m%y')}-{self.id}"

    @property
    def nb_reported_infractions(self):
        return len(self.reported_infractions)

    @property
    def reported_infractions(self):
        if self.observed_infractions is None:
            return []
        return [
            infraction
            for infraction in self.observed_infractions
            if infraction.get("is_reported", False)
        ]

    def get_reported_infractions_for_day(self, day):
        return [
            infraction
            for infraction in self.reported_infractions
            if datetime.datetime.strptime(
                infraction.get("date"), "%Y-%m-%d"
            ).date()
            == day
        ]

    @property
    def reported_infractions_labels(self):
        check_types = list(
            set(
                [
                    i.get("check_type")
                    for i in self.reported_infractions
                    if "check_type" in i
                ]
            )
        )
        labels = (
            db.session.query(RegulationCheck.label)
            .filter(RegulationCheck.type.in_(check_types))
            .all()
        )
        return [label.label for label in labels]

    def report_infractions(self):
        regulatory_alerts = get_regulatory_alerts(
            user_id=self.user.id,
            start_date=self.history_start_date,
            end_date=self.history_end_date,
        )
        regulation_computations = get_regulatory_computations(
            user_id=self.user.id,
            start_date=self.history_start_date,
            end_date=self.history_end_date,
        )
        observed_infractions = []
        for regulatory_alert in regulatory_alerts:

            extra = regulatory_alert.extra
            if not extra or not "sanction_code" in extra:
                continue

            regulation_computations_for_the_day = [
                rc
                for rc in regulation_computations
                if rc.day == regulatory_alert.day
            ]
            nb_rc_for_the_day = len(regulation_computations_for_the_day)
            if nb_rc_for_the_day == 0:
                continue
            if (
                nb_rc_for_the_day == 2
                and regulatory_alert.submitter_type != SubmitterType.ADMIN
            ):
                continue
            if (
                nb_rc_for_the_day == 1
                and regulation_computations_for_the_day[0].submitter_type
                != regulatory_alert.submitter_type
            ):
                continue
            sanction_code = extra.get("sanction_code")
            is_reportable = "NATINF" in sanction_code
            check_type = regulatory_alert.regulation_check.type
            check_unit = regulatory_alert.regulation_check.unit.value
            observed_infractions.append(
                {
                    "sanction": extra.get("sanction_code"),
                    "extra": extra,
                    "is_reportable": is_reportable,
                    "date": regulatory_alert.day.isoformat(),
                    "is_reported": is_reportable,
                    "check_type": check_type,
                    "check_unit": check_unit,
                    "business_id": regulatory_alert.business.id,
                }
            )
        self.observed_infractions = observed_infractions
        db.session.commit()

    @staticmethod
    def create_no_lic_control(controller_id, business_id):
        new_control = ControllerControl(
            control_type=ControlType.sans_lic,
            controller_id=controller_id,
            observed_infractions=get_no_lic_observed_infractions(
                datetime.date.today(), business_id
            ),
            nb_controlled_days=7,
        )
        db.session.add(new_control)
        db.session.commit()
        return new_control

    @staticmethod
    def create_lic_papier_control(
        controller_id, business_id, is_day_page_filled
    ):
        new_control = ControllerControl(
            control_type=ControlType.lic_papier,
            controller_id=controller_id,
            observed_infractions=get_no_lic_observed_infractions(
                datetime.date.today(), business_id
            )
            if not is_day_page_filled
            else [],
            nb_controlled_days=7,
        )
        db.session.add(new_control)
        db.session.commit()
        return new_control

    @staticmethod
    def get_or_create_mobilic_control(
        controller_id, user_id, qr_code_generation_time
    ):
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
            current_employments = controlled_user.active_employments_at(
                date_=qr_code_generation_time.date()
            )
            company_name = ""
            vehicle_registration_number = ""
            control_bulletin = {
                "employments_business_types": {
                    e.id: e.business.id if e.business else None
                    for e in current_employments
                }
            }
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
                    control_bulletin["siren"] = latest_mission.company.siren
                    if (
                        latest_mission.company.siren_api_info
                        and latest_mission.company.siren_api_info[
                            "etablissements"
                        ]
                    ):
                        etablissement = latest_mission.company.siren_api_info[
                            "etablissements"
                        ][-1]
                        control_bulletin["company_address"] = (
                            etablissement["adresse"]
                            + " "
                            + etablissement["codePostal"]
                        )
                    if latest_mission.vehicle:
                        vehicle_registration_number = (
                            latest_mission.vehicle.registration_number
                        )
                    if latest_mission.start_location:
                        control_bulletin[
                            "mission_address_begin"
                        ] = latest_mission.start_location.address.format()

                    current_employments_for_company = [
                        e
                        for e in current_employments
                        if e.company_id == latest_mission.company.id
                    ]
                    if len(current_employments_for_company) > 0:
                        control_bulletin[
                            "business_id"
                        ] = current_employments_for_company[0].business_id

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
                user_first_name=controlled_user.first_name,
                user_last_name=controlled_user.last_name,
                control_type=ControlType.mobilic,
                controller_id=controller_id,
                company_name=company_name,
                vehicle_registration_number=vehicle_registration_number,
                nb_controlled_days=nb_controlled_days,
                control_bulletin=control_bulletin,
            )
            db.session.add(new_control)
            db.session.commit()

            new_control.report_infractions()
            return new_control
