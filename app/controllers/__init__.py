import graphene

from app.controllers.company import CompanySignUp, Query as CompanyQuery
from app.controllers.employment import (
    CreateEmployment,
    ValidateEmployment,
    RejectEmployment,
    GetInvitation,
    RedeemInvitation,
    TerminateEmployment,
    CancelEmployment,
)
from app.controllers.expenditure import LogExpenditure, CancelExpenditure
from app.controllers.mission import (
    CreateMission,
    EndMission,
    ValidateMission,
    Query as MissionQuery,
)
from app.controllers.user import (
    UserSignUp,
    FranceConnectLogin,
    Query as UserQuery,
    ConfirmFranceConnectEmail,
    ChangeEmail,
    ActivateEmail,
)
from app.controllers.vehicle import (
    CreateVehicle,
    EditVehicle,
    TerminateVehicle,
)
from app.helpers.authentication import Auth
from app.controllers.activity import (
    LogActivity,
    EditActivity,
    CancelActivity,
)


class Activities(graphene.ObjectType):
    """
    Enregistrement des activités et frais de la journée de travail
    """

    create_mission = CreateMission.Field()
    log_activity = LogActivity.Field()
    log_expenditure = LogExpenditure.Field()
    cancel_expenditure = CancelExpenditure.Field()
    end_mission = EndMission.Field()
    validate_mission = ValidateMission.Field()
    cancel_activity = CancelActivity.Field()
    edit_activity = EditActivity.Field()


class SignUp(graphene.ObjectType):
    """
    Création de compte
    """

    user = UserSignUp.Field()
    confirm_fc_email = ConfirmFranceConnectEmail.Field()
    activate_email = ActivateEmail.Field()
    company = CompanySignUp.Field()
    redeem_invite = RedeemInvitation.Field()


class PrivateAuth(graphene.ObjectType):
    france_connect_login = FranceConnectLogin.Field()


class Account(graphene.ObjectType):
    change_email = ChangeEmail.Field()


class Employments(graphene.ObjectType):
    """
    Rattachement des utilisateurs à des entreprises
    """

    create_employment = CreateEmployment.Field()
    validate_employment = ValidateEmployment.Field()
    reject_employment = RejectEmployment.Field()
    terminate_employment = TerminateEmployment.Field()
    cancel_employment = CancelEmployment.Field()


class Vehicles(graphene.ObjectType):
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
    employments = graphene.Field(
        Employments, resolver=lambda root, info: Employments()
    )


class PrivateMutations(graphene.ObjectType):
    auth = graphene.Field(
        PrivateAuth, resolver=lambda root, info: PrivateAuth()
    )
    account = graphene.Field(Account, resolver=lambda root, info: Account())
    sign_up = graphene.Field(SignUp, resolver=lambda root, info: SignUp())
    vehicles = graphene.Field(Vehicles, resolver=lambda root, info: Vehicles())


class Queries(UserQuery, CompanyQuery, MissionQuery, graphene.ObjectType):
    """
    Requêtes de consultation qui ne modifient pas l'état du système
    """

    pass


class PrivateQueries(
    company.NonPublicQuery, GetInvitation, graphene.ObjectType
):
    pass


graphql_schema = graphene.Schema(query=Queries, mutation=Mutations)

private_graphql_schema = graphene.Schema(
    query=PrivateQueries, mutation=PrivateMutations
)
