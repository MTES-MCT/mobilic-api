import datetime

from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import Mission, MissionEnd
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    AuthenticatedUserContext,
)
from app.seed.helpers import get_time, DEFAULT_PASSWORD

ADMIN_EMAIL = "tempsdeliaison.admin@test.com"
EMPLOYEE_EMAIL = "tempsdeliaison.employee@test.com"


def run_scenario_temps_de_liaison():
    company = CompanyFactory.create(
        usual_name="Tps De Liaison Corp", siren="1122334", allow_transfers=True
    )

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Tps de Liaison",
        last_name="Admin",
    )
    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )

    employee = UserFactory.create(
        email=EMPLOYEE_EMAIL,
        password=DEFAULT_PASSWORD,
    )
    EmploymentFactory.create(
        company=company,
        submitter=admin,
        user=employee,
        has_admin_rights=False,
    )

    missions = []
    for title in [
        "Temps de liaison à ajouter",
        "Petite journée, grosse liaison",
    ]:
        mission = Mission(
            name=title,
            company=company,
            reception_time=datetime.datetime.now(),
            submitter=employee,
        )
        db.session.add(mission)
        missions.append(mission)

    with AuthenticatedUserContext(user=employee):

        ## Mission 1
        log_activity(
            submitter=employee,
            user=employee,
            mission=missions[0],
            type=ActivityType.DRIVE,
            switch_mode=False,
            reception_time=get_time(how_many_days_ago=1, hour=12),
            start_time=get_time(how_many_days_ago=1, hour=10),
            end_time=get_time(how_many_days_ago=1, hour=12),
        )

        db.session.add(
            MissionEnd(
                submitter=employee,
                reception_time=get_time(how_many_days_ago=1, hour=12),
                user=employee,
                mission=missions[0],
            )
        )
        validate_mission(
            submitter=employee, mission=missions[0], for_user=employee
        )

        ## Mission 2
        log_activity(
            submitter=employee,
            user=employee,
            mission=missions[1],
            type=ActivityType.DRIVE,
            switch_mode=False,
            reception_time=get_time(how_many_days_ago=2, hour=16),
            start_time=get_time(how_many_days_ago=2, hour=14),
            end_time=get_time(how_many_days_ago=2, hour=16),
        )

        db.session.add(
            MissionEnd(
                submitter=employee,
                reception_time=get_time(how_many_days_ago=2, hour=16),
                user=employee,
                mission=missions[1],
            )
        )
        validate_mission(
            submitter=employee, mission=missions[1], for_user=employee
        )

    with AuthenticatedUserContext(user=admin):
        ## Adding temps de liaison for second mission
        log_activity(
            submitter=admin,
            user=employee,
            mission=missions[1],
            type=ActivityType.TRANSFER,
            switch_mode=False,
            reception_time=get_time(how_many_days_ago=2, hour=20),
            start_time=get_time(how_many_days_ago=2, hour=4),
            end_time=get_time(how_many_days_ago=2, hour=14),
        )

    db.session.commit()
