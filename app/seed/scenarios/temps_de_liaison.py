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

ADMIN_USER_NAME = "tempsdeliaison.admin@test.com"

YESTERDAY = datetime.date.today() - datetime.timedelta(days=1)
START_HOUR = datetime.time(hour=14, minute=0)
END_HOUR = datetime.time(hour=15, minute=0)
START_TIME = datetime.datetime.combine(YESTERDAY, START_HOUR)
END_TIME = datetime.datetime.combine(YESTERDAY, END_HOUR)


def run_scenario_temps_de_liaison():
    company = CompanyFactory.create(
        usual_name="Tps De Liaison Corp", siren="1122334", allow_transfers=True
    )

    admin = UserFactory.create(
        email=ADMIN_USER_NAME,
        password="password",
        first_name="Tps de Liaison",
        last_name="Admin",
    )
    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )

    employee = UserFactory.create(
        email=f"tempsdeliaison.employee@test.com",
        password="password",
    )
    EmploymentFactory.create(
        company=company,
        submitter=admin,
        user=employee,
        has_admin_rights=False,
    )

    mission = Mission(
        name=f"Mission Temps De Liaison",
        company=company,
        reception_time=datetime.datetime.now(),
        submitter=employee,
    )
    db.session.add(mission)

    with AuthenticatedUserContext(user=employee):
        log_activity(
            submitter=employee,
            user=employee,
            mission=mission,
            type=ActivityType.DRIVE,
            switch_mode=False,
            reception_time=END_TIME,
            start_time=START_TIME,
            end_time=END_TIME,
        )

        db.session.add(
            MissionEnd(
                submitter=employee,
                reception_time=END_TIME,
                user=employee,
                mission=mission,
            )
        )
        validate_mission(
            submitter=employee, mission=mission, for_user=employee
        )
    db.session.commit()
