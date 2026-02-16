from flask import g
from sqlalchemy import func

from app import app, db
from app.models.controller_user import ControllerUser
from app.helpers.validation import clean_email_string
from app.helpers.errors import (
    AgentConnectIdpNotAllowedError,
    AgentConnectOrganizationalUnitError,
)


def check_idp_allowed(ac_info):
    allowed_idp_ids = app.config["PC_ALLOWED_IDP_IDS"]
    idp_id = ac_info.get("idp_id")
    if not allowed_idp_ids or idp_id not in allowed_idp_ids:
        raise AgentConnectIdpNotAllowedError(
            f"Identity provider '{idp_id}' is not allowed for controller login"
        )


def create_controller_user(ac_info):
    if not ac_info.get("organizational_unit"):
        raise AgentConnectOrganizationalUnitError(
            "Controlleur must be linked to an organizational unit in agent connect"
        )
    controller = ControllerUser(
        agent_connect_id=ac_info.get("sub"),
        first_name=ac_info.get("given_name"),
        last_name=ac_info.get("usual_name"),
        email=clean_email_string(ac_info.get("email")),
        agent_connect_info=ac_info,
        organizational_unit=ac_info.get("organizational_unit"),
    )
    db.session.add(controller)
    db.session.flush()

    g.controller = controller

    return controller


def get_controller_from_ac_info(ac_info):
    ac_id = ac_info.get("sub")
    email = ac_info.get("email")

    controller_user = ControllerUser.query.filter(
        ControllerUser.agent_connect_id == ac_id
    ).one_or_none()

    if controller_user is not None:
        return controller_user

    return ControllerUser.query.filter(
        func.lower(ControllerUser.email) == func.lower(email)
    ).one_or_none()
