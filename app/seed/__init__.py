import sys

from app import db
from app.helpers.oauth.models import (
    OAuth2Client,
    ThirdPartyClientCompany,
    ThirdPartyClientEmployment,
)
from app.models import (
    ActivityVersion,
    Comment,
    Company,
    CompanyKnownAddress,
    ControllerRefreshToken,
    ControllerUser,
    Email,
    Employment,
    Expenditure,
    LocationEntry,
    Mission,
    MissionEnd,
    MissionValidation,
    RefreshToken,
    RegulationComputation,
    RegulatoryAlert,
    User,
    UserReadToken,
    Vehicle,
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

    ThirdPartyClientEmployment.query.delete()
    ThirdPartyClientCompany.query.delete()
    OAuth2Client.query.delete()

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
    RegulatoryAlert.query.delete()
    RegulationComputation.query.delete()
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
