import datetime
import random

from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import Business
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    AuthenticatedUserContext,
)
from app.seed.helpers import (
    add_employee,
    get_time,
    create_mission,
    DEFAULT_PASSWORD,
    create_vehicle,
    create_address,
    end_mission,
)

ADMIN_EMAIL = "test.charge@admin.com"
NB_EMPLOYEES = 2
NB_HISTORY_DELETED = 2
NB_VEHICLES = 10
NB_ADDRESSES = 10


def run_scenario_lot_of_deleted_missions():
    business = Business.query.first()
    company = CompanyFactory.create(
        usual_name=f"Test Charge",
        siren=f"1000001",
        number_workers=NB_EMPLOYEES + 1,
        business=business,
    )
    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Prenom",
        last_name="Nom",
    )
    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )
    vehicles = [create_vehicle(company=company) for _ in range(NB_VEHICLES)]
    db.session.commit()

    employees = [
        add_employee(
            company=company,
            admin=admin,
        )
        for _ in range(NB_EMPLOYEES)
    ]
    db.session.commit()

    addresses = [create_address(company=company) for _ in range(NB_ADDRESSES)]
    db.session.commit()

    missions = []
    for employee in employees:

        for nb_days_ago in range(NB_HISTORY_DELETED):

            # create a mission
            mission = create_mission(
                name=f"Mission {nb_days_ago}",
                company=company,
                time=datetime.datetime.now(),
                submitter=employee,
                vehicle=random.choice(vehicles),
                address=random.choice(addresses),
                add_location_entry=True,
            )
            db.session.commit()
            with AuthenticatedUserContext(user=employee):
                log_activity(
                    submitter=employee,
                    user=employee,
                    mission=mission,
                    type=ActivityType.DRIVE,
                    switch_mode=False,
                    reception_time=get_time(
                        how_many_days_ago=nb_days_ago + 1, hour=15
                    ),
                    start_time=get_time(
                        how_many_days_ago=nb_days_ago + 1, hour=14
                    ),
                    end_time=get_time(
                        how_many_days_ago=nb_days_ago + 1, hour=15
                    ),
                )
                end_mission(
                    mission=mission,
                    submitter=employee,
                    for_user=employee,
                    time=get_time(how_many_days_ago=nb_days_ago + 1, hour=15),
                    address=random.choice(addresses),
                    add_location_entry=True,
                )
                validate_mission(
                    submitter=employee,
                    mission=mission,
                    for_user=employee,
                )
            db.session.commit()

            missions.append(mission)

    from app.tests.helpers import make_authenticated_request, ApiRequests

    # Admin cancels missions
    for mission in missions:
        make_authenticated_request(
            time=get_time(how_many_days_ago=1, hour=17),
            submitter_id=admin.id,
            query=ApiRequests.cancel_mission,
            variables=dict(
                mission_id=mission.id,
                user_id=mission.submitter_id,
            ),
        )
