from flask import g

from app import app, db
from app.models.controller_user import ControllerUser
from app.models.regulation_check import UnitType, RegulationCheckType


def create_controller_user(ac_info):
    controller = ControllerUser(
        agent_connect_id=ac_info.get("sub"),
        first_name=ac_info.get("given_name"),
        last_name=ac_info.get("usual_name"),
        email=ac_info.get("email"),
        agent_connect_info=ac_info,
        organizational_unit=ac_info.get("organizational_unit"),
    )
    db.session.add(controller)
    db.session.flush()

    message = f"Signed up new controller {controller}"

    g.controller = controller
    app.logger.info(
        message,
        extra={
            "post_to_mattermost": True,
            "log_title": "New controller signup",
            "emoji": ":female-police-officer:",
        },
    )

    return controller


def get_controller_from_ac_info(ac_info):
    agent_connect_id = ac_info.get("sub")

    return ControllerUser.query.filter(
        ControllerUser.agent_connect_id == agent_connect_id
    ).one_or_none()


def get_no_lic_observed_infractions(control_date):
    return [
        {
            "sanction": "NATINF 23103",
            "date": control_date.isoformat(),
            "is_reportable": True,
            "is_reported": True,
            "extra": None,
            "check_unit": UnitType.DAY,
            "check_type": RegulationCheckType.NO_LIC,
        }
    ]
