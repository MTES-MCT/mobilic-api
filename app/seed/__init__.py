import sys

from app import db
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
    CompanyKnownAddress,
    Expenditure,
    Comment,
    ControllerRefreshToken,
    ControllerUser,
)
from app.models.activity import Activity
from app.models.controller_control import ControllerControl
from app.seed.factories import (
    UserFactory,
    CompanyFactory,
    EmploymentFactory,
    ControllerUserFactory,
)
from app.seed.helpers import AuthenticatedUserContext
from app.seed.scenarios import run_scenario_busy_admin
from app.seed.scenarios import scenarios
from config import MOBILIC_ENV


def exit_if_prod():
    if MOBILIC_ENV == "prod":
        print("Seeding not available in prod environment")
        sys.exit(0)


def clean():
    exit_if_prod()

    print("------ CLEANING DATA -------")

    Expenditure.query.delete()
    ActivityVersion.query.delete()
    Activity.query.delete()

    Comment.query.delete()
    MissionValidation.query.delete()
    MissionEnd.query.delete()
    LocationEntry.query.delete()
    Mission.query.delete()

    CompanyKnownAddress.query.delete()
    Employment.query.delete()
    Vehicle.query.delete()
    Company.query.delete()

    ControllerControl.query.delete()

    RefreshToken.query.delete()
    UserReadToken.query.delete()
    Email.query.delete()
    User.query.delete()

    ControllerRefreshToken.query.delete()
    ControllerUser.query.delete()
    db.session.commit()


def seed():
    exit_if_prod()

    print("###########################")
    print("###### SEEDING DATA #######")
    print("###########################")

    for scenario in scenarios:
        scenario.run()
