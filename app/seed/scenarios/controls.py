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

    company = CompanyFactory.create(
        usual_name="Controlled Corp", siren="77464376"
    )
    admin = UserFactory.create(
        password=DEFAULT_PASSWORD,
    )
    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )
    vehicle = Vehicle(
        registration_number=f"XXX-001-ABC",
        alias=f"Vehicule 1",
        submitter=admin,
        company_id=company.id,
    )
    db.session.add(vehicle)

    employees = [
        UserFactory.create(
            first_name=f"Michel {i + 1}", last_name=f"Pickford {i + 1}"
        )
        for i in range(2)
    ]
    for e in employees:
        EmploymentFactory.create(
            company=company,
            submitter=admin,
            user=e,
            has_admin_rights=False,
        )

    for days_ago in range(3, -1, -1):
        for e in employees:
            temp_mission = Mission(
                name=f"Mission",
                company=company,
                reception_time=get_time(how_many_days_ago=days_ago, hour=8),
                submitter=e,
                vehicle_id=vehicle.id,
            )
            db.session.add(temp_mission)
            db.session.commit()
            with AuthenticatedUserContext(user=e):
                activity = log_activity(
                    submitter=e,
                    user=e,
                    mission=temp_mission,
                    type=ActivityType.DRIVE,
                    switch_mode=True,
                    reception_time=get_time(
                        how_many_days_ago=days_ago, hour=8
                    ),
                    start_time=get_time(how_many_days_ago=days_ago, hour=8),
                )
                ControllerControl.get_or_create_mobilic_control(
                    controller_id=controller_user.id,
                    user_id=e.id,
                    qr_code_generation_time=get_time(
                        how_many_days_ago=days_ago, hour=9
                    ),
                )
                end_time = get_time(how_many_days_ago=days_ago, hour=10)
                edit_activity(activity.id, cancel=False, end_time=end_time)
                db.session.add(
                    MissionEnd(
                        submitter=e,
                        reception_time=get_time(
                            how_many_days_ago=days_ago, hour=10
                        ),
                        user=e,
                        mission=temp_mission,
                    )
                )
