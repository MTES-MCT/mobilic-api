from flask import g

from app import app, db
from app.models.controller_user import ControllerUser


def create_controller_user(ac_info):
    controller = ControllerUser(
        agent_connect_id=ac_info.get("sub"),
        first_name=ac_info.get("given_name"),
        last_name=ac_info.get("family_name"),
        email=ac_info.get("email"),
        agent_connect_info=ac_info,
        organizational_unit="mobilic",
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
