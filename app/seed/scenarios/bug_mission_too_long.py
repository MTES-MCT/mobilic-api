from datetime import time, datetime

from app import db
from app.domain.log_activities import log_activity
from app.models import (
    Mission,
)
from app.models.activity import ActivityType
from app.seed import CompanyFactory, UserFactory, EmploymentFactory
from app.seed.helpers import AuthenticatedUserContext

ADMIN_EMAIL = "too_long@admin.com"
EMPLOYEE_1_EMAIL = "too_long@employee.com"
MISSION_START = datetime(2022, 4, 10)


def run_scenario_too_long():

    ## Two companies
    company = CompanyFactory.create(
        usual_name="Company Too Long",
        siren=f"0000185",
    )

    ## An admin for both companies
    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password="password",
        first_name="TooLong",
        last_name="Admin",
    )
    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )

    employee = UserFactory.create(
        email=EMPLOYEE_1_EMAIL,
        password="password",
        first_name=f"Dennis",
        last_name=f"Rodman",
    )
    EmploymentFactory.create(
        company=company,
        submitter=admin,
        user=employee,
        has_admin_rights=False,
    )

    mission = Mission(
        name=f"Mission Way Too long",
        company=company,
        reception_time=datetime.combine(
            MISSION_START, time(hour=10, minute=0)
        ),
        submitter=employee,
    )
    db.session.add(mission)
    db.session.commit()

    with AuthenticatedUserContext(user=employee):
        log_activity(
            submitter=employee,
            user=employee,
            mission=mission,
            type=ActivityType.DRIVE,
            switch_mode=False,
            reception_time=datetime.combine(
                MISSION_START, time(hour=11, minute=0)
            ),
            start_time=datetime.combine(
                MISSION_START, time(hour=10, minute=0)
            ),
        )

    db.session.commit()
