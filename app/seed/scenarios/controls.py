import datetime

from app import db
from app.controllers.activity import edit_activity
from app.domain.log_activities import log_activity
from app.models import Vehicle, Mission, MissionEnd, User
from app.models.activity import ActivityType
from app.models.controller_control import ControllerControl
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    ControllerUserFactory,
)
from app.seed.helpers import (
    get_time,
    AuthenticatedUserContext,
    DEFAULT_PASSWORD,
)


def run_scenario_controls():
    controller_user = ControllerUserFactory.create(
        email="test@abcd.com",
        agent_connect_id="18fe42b1cb10db11339baf77d8974821bcd594bc225989c3b0adfc6b05f197fd",
    )

    ## Control previous employees
    users = User.query.all()
    for u in users:
        ControllerControl.get_or_create_mobilic_control(
            controller_id=controller_user.id,
            user_id=u.id,
            qr_code_generation_time=get_time(how_many_days_ago=0, hour=0),
        )
