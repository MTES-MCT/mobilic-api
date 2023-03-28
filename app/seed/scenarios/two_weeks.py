from app import db
from app.domain.log_activities import log_activity
from app.domain.validation import validate_mission
from app.models import (
    MissionEnd,
    Mission,
)
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    AuthenticatedUserContext,
)
from app.seed.helpers import get_time, DEFAULT_PASSWORD

ADMIN_EMAIL = "nonstop@test.com"
EMPLOYEE_EMAIL = "employee.nonstop@test.com"


def run_scenario_non_stop():
    company = CompanyFactory.create(
        usual_name=f"Non Stop Ltd", siren=f"00000909"
    )

    admin = UserFactory.create(
        email=ADMIN_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name="Non Stop",
        last_name="Boss",
    )

    EmploymentFactory.create(
        company=company, submitter=admin, user=admin, has_admin_rights=True
    )

    employee = UserFactory.create(
        email=EMPLOYEE_EMAIL,
        password=DEFAULT_PASSWORD,
        first_name=f"Non",
        last_name=f"Stop",
    )
    EmploymentFactory.create(
        company=company,
        submitter=admin,
        user=employee,
        has_admin_rights=False,
    )

    mission = Mission(
        name="Longue mission",
        company=company,
        reception_time=get_time(how_many_days_ago=24, hour=8),
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
            reception_time=get_time(how_many_days_ago=1, hour=8),
            start_time=get_time(how_many_days_ago=24, hour=8),
            end_time=get_time(how_many_days_ago=1, hour=8),
        )
        db.session.add(
            MissionEnd(
                submitter=employee,
                reception_time=get_time(how_many_days_ago=1, hour=8),
                user=employee,
                mission=mission,
            )
        )
        validate_mission(
            submitter=employee,
            mission=mission,
            for_user=employee,
        )
    db.session.commit()
