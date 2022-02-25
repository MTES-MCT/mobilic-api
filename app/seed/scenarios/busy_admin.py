import datetime
import sys

from app import db
from app.domain.log_activities import log_activity
from app.models import Mission
from app.models.activity import ActivityType
from app.seed import (
    CompanyFactory,
    UserFactory,
    EmploymentFactory,
    AuthenticatedUserContext,
)

NB_COMPANIES = 10
NB_EMPLOYEES = 10
ADMIN_USER_NAME = "busy.admin@test.com"

YESTERDAY = datetime.date.today() - datetime.timedelta(days=1)
START_HOUR = datetime.time(hour=14, minute=0)
END_HOUR = datetime.time(hour=15, minute=0)
START_TIME = datetime.datetime.combine(YESTERDAY, START_HOUR)
END_TIME = datetime.datetime.combine(YESTERDAY, END_HOUR)


def run_scenario_busy_admin():
    companies = [
        CompanyFactory.create(
            usual_name=f"Busy Corp {i + 1}", siren=f"000000{i}"
        )
        for i in range(NB_COMPANIES)
    ]

    admin = UserFactory.create(
        email=ADMIN_USER_NAME,
        password="password",
        first_name="Busy",
        last_name="Admin",
    )

    for idx_company, company in enumerate(companies):
        EmploymentFactory.create(
            company=company, submitter=admin, user=admin, has_admin_rights=True
        )
        for i in range(NB_EMPLOYEES):
            employee = UserFactory.create(
                email=f"busy.employee{i + 1}@busycorp{idx_company + 1}.com",
                password="password",
                first_name=f"Employee {i + 1}",
                last_name=f"Corp {idx_company + 1}",
            )
            EmploymentFactory.create(
                company=company,
                submitter=admin,
                user=employee,
                has_admin_rights=False,
            )
            mission = Mission(
                name=f"Mission Test {idx_company + 1}:{i + 1}",
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

    db.session.commit()
