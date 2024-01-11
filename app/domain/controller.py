from flask import g

from app import app, db
from app.models.controller_user import ControllerUser


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

    g.controller = controller

    return controller


def get_controller_from_ac_info(ac_info):
    email = ac_info.get("email")

    return ControllerUser.query.filter(
        ControllerUser.email == email
    ).one_or_none()
