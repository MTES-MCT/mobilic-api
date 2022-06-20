import graphene

from app.controllers.comment import LogComment, CancelComment
from app.controllers.company import (
    CompanySignUp,
    Query as CompanyQuery,
    EditCompanySettings,
)
from app.controllers.user_read import Query as UserReadTokenQuery
from app.controllers.employment import (
    CreateEmployment,
    ValidateEmployment,
    RejectEmployment,
    GetInvitation,
    RedeemInvitation,
    TerminateEmployment,
    CancelEmployment,
    SendInvitationReminder,
    CreateWorkerEmploymentsFromEmails,
    ChangeEmployeeRole,
)
from app.controllers.expenditure import LogExpenditure, CancelExpenditure
from app.controllers.location_entry import (
    CreateCompanyKnownAddress,
    EditCompanyKnownAddress,
    TerminateCompanyKnownAddress,
    LogMissionLocation,
    RegisterKilometerAtLocation,
)
from app.controllers.mission import (
    CreateMission,
    EndMission,
    ValidateMission,
    Query as MissionQuery,
    UpdateMissionVehicle,
    ChangeMissionName,
)
from app.controllers.user import (
    UserSignUp,
    FranceConnectLogin,
    Query as UserQuery,
    ConfirmFranceConnectEmail,
    ChangeEmail,
    ActivateEmail,
    ResetPassword,
    RequestPasswordReset,
    DisableWarning,
    ResendActivationEmail,
)
from app.controllers.vehicle import (
    CreateVehicle,
    EditVehicle,
    TerminateVehicle,
)
from app.helpers.authentication import Auth, CheckQuery
from app.controllers.activity import (
    LogActivity,
    EditActivity,
    CancelActivity,
    BulkActivity,
)
from app.models.address import AddressOutput, Address


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
    log_comment = LogComment.Field()
    cancel_comment = CancelComment.Field()
    cancel_activity = CancelActivity.Field()
    bulk_activities = BulkActivity.Field()
    edit_activity = EditActivity.Field()
    log_location = LogMissionLocation.Field()
    update_mission_vehicle = UpdateMissionVehicle.Field()
    change_mission_name = ChangeMissionName.Field()
    register_kilometer_at_location = RegisterKilometerAtLocation.Field()


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
    reset_password = ResetPassword.Field()
    request_reset_password = RequestPasswordReset.Field()
    resend_activation_email = ResendActivationEmail.Field()
    disable_warning = DisableWarning.Field()


class Employments(graphene.ObjectType):
    """
    Rattachement des utilisateurs à des entreprises
    """

    create_employment = CreateEmployment.Field()
    validate_employment = ValidateEmployment.Field()
    reject_employment = RejectEmployment.Field()
    terminate_employment = TerminateEmployment.Field()
    cancel_employment = CancelEmployment.Field()
    send_invitation_reminder = SendInvitationReminder.Field()
    batch_create_worker_employments = CreateWorkerEmploymentsFromEmails.Field()
    change_employee_role = ChangeEmployeeRole.Field()


class Vehicles(graphene.ObjectType):
    """
    Gestion des informations de l'entreprise
    """

    create_vehicle = CreateVehicle.Field()
    edit_vehicle = EditVehicle.Field()
    terminate_vehicle = TerminateVehicle.Field()


class Locations(graphene.ObjectType):
    create_known_address = CreateCompanyKnownAddress.Field()
    edit_known_address = EditCompanyKnownAddress.Field()
    terminate_known_address = TerminateCompanyKnownAddress.Field()


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
    locations = graphene.Field(
        Locations, resolver=lambda root, info: Locations()
    )
    edit_company_settings = EditCompanySettings.Field()


class Queries(
    UserQuery, CheckQuery, CompanyQuery, MissionQuery, graphene.ObjectType
):
    """
    Requêtes de consultation qui ne modifient pas l'état du système
    """

    pass


class PrivateQueries(
    company.NonPublicQuery,
    GetInvitation,
    UserReadTokenQuery,
    graphene.ObjectType,
):
    pass


graphql_schema = graphene.Schema(
    query=Queries, mutation=Mutations, types=[AddressOutput]
)

private_graphql_schema = graphene.Schema(
    query=PrivateQueries, mutation=PrivateMutations, types=[AddressOutput]
)

from app.controllers.contacts import *
