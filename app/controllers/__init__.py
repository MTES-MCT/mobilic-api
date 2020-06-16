import graphene

from app.controllers.comment import LogComment
from app.controllers.mission import (
    BeginMission,
    EndMission,
    ValidateMission,
    EditMissionExpenditures,
)
from app.controllers.team import EnrollOrReleaseTeamMate
from app.controllers.vehicle import (
    CreateVehicle,
    EditVehicle,
    TerminateVehicle,
)
from app.controllers.vehicle_booking import LogVehicleBooking
from app.helpers.authentication import Auth
from app.controllers.activity import LogActivity, EditActivity
import app.controllers.user
import app.controllers.company


class Activities(graphene.ObjectType):
    """
    Enregistrement des activités, temps et autres informations importantes de la journée de travail
    """

    begin_mission = BeginMission.Field()
    log_activity = LogActivity.Field()
    end_mission = EndMission.Field()
    validate_mission = ValidateMission.Field()
    edit_activity = EditActivity.Field()
    book_vehicle = LogVehicleBooking.Field()
    enroll_or_release_team_mate = EnrollOrReleaseTeamMate.Field()
    log_comment = LogComment.Field()
    edit_mission_expenditures = EditMissionExpenditures.Field()


class SignUp(graphene.ObjectType):
    """
    Création de compte
    """

    user = user.UserSignUp.Field()
    company = company.CompanySignUp.Field()


class Admin(graphene.ObjectType):
    """
    Gestion des informations de l'entreprise
    """

    create_vehicle = CreateVehicle.Field()
    edit_vehicle = EditVehicle.Field()
    terminate_vehicle = TerminateVehicle.Field()


class Mutations(graphene.ObjectType):
    """
    Entrée de nouvelles informations dans le système
    """

    auth = graphene.Field(Auth, resolver=lambda root, info: Auth())
    activities = graphene.Field(
        Activities, resolver=lambda root, info: Activities()
    )
    sign_up = graphene.Field(SignUp, resolver=lambda root, info: SignUp())
    admin = graphene.Field(Admin, resolver=lambda root, info: Admin())


class Queries(user.Query, company.Query, graphene.ObjectType):
    """
    Requêtes de consultation qui ne modifient pas l'état du système
    """

    pass


graphql_schema = graphene.Schema(query=Queries, mutation=Mutations)
