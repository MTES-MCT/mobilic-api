import datetime

from app import db
from app.domain.log_activities import log_activity
from app.models import Vehicle, Mission, MissionEnd
from app.models.activity import ActivityType
from app.models.controller_control import ControllerControl
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    ControllerUserFactory,
)
from app.seed.helpers import get_time, AuthenticatedUserContext


def run_scenario_controls():
    company = CompanyFactory.create(
        usual_name="Controlled Corp", siren="77464376"
    )
    admin = UserFactory.create(
        password="password",
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
    controller_user = ControllerUserFactory.create(email="controller@test.com")

    for days_ago in range(30, -1, -1):
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
                log_activity(
                    submitter=e,
                    user=e,
                    mission=temp_mission,
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=get_time(
                        how_many_days_ago=days_ago, hour=10
                    ),
                    start_time=get_time(how_many_days_ago=days_ago, hour=8),
                    end_time=get_time(how_many_days_ago=days_ago, hour=10),
                )
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
            ControllerControl.get_or_create_mobilic_control(
                controller_id=controller_user.id,
                user_id=e.id,
                qr_code_generation_time=get_time(
                    how_many_days_ago=days_ago, hour=9
                ),
            )
