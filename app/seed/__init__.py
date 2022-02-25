import sys

from app import db, app
from app.models import (
    User,
    Employment,
    Company,
    RefreshToken,
    Mission,
    ActivityVersion,
    MissionValidation,
    MissionEnd,
    LocationEntry,
    Vehicle,
    Email,
    UserReadToken,
)
from app.models.activity import Activity
from app.seed.factories import (
    UserFactory,
    CompanyFactory,
    EmploymentFactory,
)
from app.seed.helpers import AuthenticatedUserContext
from app.seed.scenarios import run_scenario_busy_admin
from config import MOBILIC_ENV
from app.seed.scenarios import scenarios


def exit_if_prod():
    if MOBILIC_ENV == "prod":
        print("Seeding not available in prod environment")
        sys.exit(0)


# @app.cli.command(with_appcontext=True)
def clean():
    exit_if_prod()

    print("------ CLEANING DATA -------")
    # CAN WE USE CASCADE TO DELETE ALL OF THIS ??
    ActivityVersion.query.delete()
    Activity.query.delete()
    MissionValidation.query.delete()
    MissionEnd.query.delete()
    LocationEntry.query.delete()
    Mission.query.delete()
    Employment.query.delete()
    Vehicle.query.delete()
    Company.query.delete()
    RefreshToken.query.delete()
    UserReadToken.query.delete()
    Email.query.delete()
    User.query.delete()
    db.session.commit()


# @app.cli.command(with_appcontext=True)
def seed():
    exit_if_prod()

    print("###########################")
    print("###### SEEDING DATA #######")
    print("###########################")

    for scenario in scenarios:
        scenario.run()
