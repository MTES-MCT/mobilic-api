import sys
import datetime
from unittest.mock import patch, MagicMock

from app import app, db
from app.domain.log_activities import log_activity
from app.models import (
    User,
    Employment,
    Company,
    RefreshToken,
    Mission,
    ActivityVersion,
)
from app.models.activity import ActivityType, Activity
from app.seed.factories import (
    UserFactory,
    CompanyFactory,
    EmploymentFactory,
)
from app.seed.helpers import AuthenticatedUserContext
from config import MOBILIC_ENV

NB_COMPANIES = 10
NB_EMPLOYEES = 10
YESTERDAY = datetime.date.today() - datetime.timedelta(days=1)
START_HOUR = datetime.time(hour=14, minute=0)
END_HOUR = datetime.time(hour=15, minute=0)
START_TIME = datetime.datetime.combine(YESTERDAY, START_HOUR)
END_TIME = datetime.datetime.combine(YESTERDAY, END_HOUR)


# class AuthenticatedUserContext:
#     def __init__(self, user=None):
#         self.mocked_authenticated_user = None
#         self.mocked_token_verification = None
#         if user:
#             self.mocked_token_verification = patch(
#                 "app.helpers.authentication.verify_jwt_in_request",
#                 new=MagicMock(return_value=None),
#             )
#             self.mocked_authenticated_user = patch(
#                 "flask_jwt_extended.utils.get_current_user",
#                 new=MagicMock(return_value=user),
#             )
#
#     def __enter__(self):
#         if self.mocked_authenticated_user:
#             self.mocked_token_verification.__enter__()
#             self.mocked_authenticated_user.__enter__()
#         return self
#
#     def __exit__(self, *args):
#         if self.mocked_token_verification:
#             self.mocked_authenticated_user.__exit__(*args)
#             self.mocked_token_verification.__exit__(*args)


def exit_if_prod():
    if MOBILIC_ENV == "prod":
        print("Seeding not available in prod environment")
        sys.exit(0)


@app.cli.command(with_appcontext=True)
def clean():
    exit_if_prod()

    print("------ CLEANING DATA -------")
    ActivityVersion.query.delete()
    Activity.query.delete()
    Mission.query.delete()
    Employment.query.delete()
    Company.query.delete()
    RefreshToken.query.delete()
    User.query.delete()
    db.session.commit()


@app.cli.command(with_appcontext=True)
def seed():
    exit_if_prod()

    print("------ SEEDING DATA -------")

    print(f"Creating {NB_COMPANIES} companies...")
    companies = [
        CompanyFactory.create(
            usual_name=f"Busy Corp {i + 1}", siren=f"000000{i}"
        )
        for i in range(NB_COMPANIES)
    ]
    print(f"{NB_COMPANIES} companies created.")

    print(f"Creating admin...")
    admin = UserFactory.create(
        email="busy.admin@test.com",
        password="password",
        first_name="Busy",
        last_name="Admin",
    )
    print(f"Admin created.")

    print(f"Creating {NB_EMPLOYEES} employees per companies.")
    print(f"Each employee will create 1 mission and log 1 hour of work in it.")
    for idx_company, company in enumerate(companies):
        EmploymentFactory.create(
            company=company, submitter=admin, user=admin, has_admin_rights=True
        )
        for i in range(NB_EMPLOYEES):
            employee = UserFactory.create(
                email=f"busy.employee{i+1}@busycorp{idx_company+1}.com",
                password="password",
                first_name=f"Employee {i+1}",
                last_name=f"Corp {idx_company+1}",
            )
            EmploymentFactory.create(
                company=company,
                submitter=admin,
                user=employee,
                has_admin_rights=False,
            )
            mission = Mission(
                name=f"Mission Test {idx_company+1}:{i+1}",
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

        sys.stdout.write(f"\r{idx_company + 1} / {NB_COMPANIES}")
    sys.stdout.flush()
    db.session.commit()

    print(f"\nAll done.")
