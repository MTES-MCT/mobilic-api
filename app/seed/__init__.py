import sys

from app import db
from app.helpers.oauth.models import (
    OAuth2Client,
    ThirdPartyApiKey,
    ThirdPartyClientCompany,
    ThirdPartyClientEmployment,
)
from app.models import (
    Activity,
    ActivityVersion,
    Comment,
    Company,
    CompanyCertification,
    CompanyKnownAddress,
    CompanyStats,
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
    ScenarioTesting,
    User,
    UserReadToken,
    Vehicle,
    Team,
    UserSurveyActions,
    UserAgreement,
    MissionAutoValidation,
)
from app.models.controller_control import ControllerControl
from app.models.notification import Notification
from app.seed.factories import (
    UserFactory,
    CompanyFactory,
    EmploymentFactory,
    ControllerUserFactory,
)
from app.seed.helpers import AuthenticatedUserContext
from app.seed.scenarios import run_scenario_busy_admin
from app.seed.scenarios import scenarios
from app.services.init_user_agreement import init_user_agreement
from config import MOBILIC_ENV


def exit_if_prod():
    if MOBILIC_ENV == "prod":
        print("Seeding not available in prod environment")
        sys.exit(0)


def exit_if_no_local():
    if MOBILIC_ENV != "dev":
        print("Seeding available ONLY on local environment")
        sys.exit(0)


def clean():
    exit_if_no_local()

    print("------ CLEANING DATA -------")

    ThirdPartyClientEmployment.query.delete()
    ThirdPartyClientCompany.query.delete()
    ThirdPartyApiKey.query.delete()
    OAuth2Client.query.delete()

    Expenditure.query.delete()
    ActivityVersion.query.delete()
    Activity.query.delete()

    Comment.query.delete()
    MissionValidation.query.delete()
    MissionAutoValidation.query.delete()
    MissionEnd.query.delete()
    LocationEntry.query.delete()
    Mission.query.delete()

    db.session.execute(
        """
        DELETE FROM team_admin_user;
        DELETE FROM team_known_address;
        DELETE FROM team_vehicle;
        """
    )
    Email.query.delete()
    CompanyStats.query.delete()
    CompanyCertification.query.delete()
    CompanyKnownAddress.query.delete()
    Employment.query.delete()
    Team.query.delete()
    Vehicle.query.delete()
    Company.query.delete()

    RefreshToken.query.delete()
    UserReadToken.query.delete()
    RegulatoryAlert.query.delete()
    RegulationComputation.query.delete()

    ControllerControl.query.delete()
    ControllerRefreshToken.query.delete()
    ControllerUser.query.delete()

    Notification.query.delete()

    UserAgreement.query.delete()
    ScenarioTesting.query.delete()
    UserSurveyActions.query.delete()
    User.query.delete()
    db.session.commit()


def seed():
    exit_if_prod()

    print("###########################")
    print("###### SEEDING DATA #######")
    print("###########################")

    for scenario in scenarios:
        scenario.run()

    init_user_agreement(session=db.session, cgu_version="v2.0")
    db.session.commit()
