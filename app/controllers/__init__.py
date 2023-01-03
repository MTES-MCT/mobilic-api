import graphene
from app.controllers.activity import BulkActivity as BulkActivityQuery
from app.controllers.activity import CancelActivity, EditActivity, LogActivity
from app.controllers.comment import CancelComment, LogComment
from app.controllers.company import (
    CompaniesSignUp,
    CompanySignUp,
    EditCompanySettings,
    CompanySoftwareRegistration,
)
from app.controllers.company import Query as CompanyQuery
from app.controllers.controller import AgentConnectLogin, ControllerScanCode
from app.controllers.controller import Query as ControllerUserQuery
from app.controllers.employment import (
    CancelEmployment,
    ChangeEmployeeRole,
    CreateEmployment,
    CreateWorkerEmploymentsFromEmails,
    GetInvitation,
    RedeemInvitation,
    RejectEmployment,
    SendInvitationReminder,
    TerminateEmployment,
    ValidateEmployment,
    SyncThirdPartyEmployees,
)
from app.controllers.expenditure import CancelExpenditure, LogExpenditure
from app.controllers.location_entry import (
    CreateCompanyKnownAddress,
    EditCompanyKnownAddress,
    LogMissionLocation,
    RegisterKilometerAtLocation,
    TerminateCompanyKnownAddress,
)
from app.controllers.mission import (
    CancelMission,
    ChangeMissionName,
    CreateMission,
    EndMission,
)
from app.controllers.mission import Query as MissionQuery
from app.controllers.mission import UpdateMissionVehicle, ValidateMission
from app.controllers.user import (
    ActivateEmail,
    ChangeEmail,
    ChangeTimezone,
    ConfirmFranceConnectEmail,
    DisableWarning,
    FranceConnectLogin,
)
from app.controllers.user import Query as UserQuery
from app.controllers.user import (
    RequestPasswordReset,
    ResendActivationEmail,
    ResetPassword,
    UserSignUp,
)
from app.controllers.user_read import Query as UserReadTokenQuery
from app.controllers.oauth_token import Query as UserOAuthTokenQuery
from app.controllers.oauth_client import Query as UserOAuthClientQuery
from app.controllers.vehicle import (
    CreateVehicle,
    EditVehicle,
    TerminateVehicle,
)
from app.helpers.authentication import Auth, CheckQuery
from app.models.address import AddressOutput


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
    edit_activity = EditActivity.Field()
    log_location = LogMissionLocation.Field()
    update_mission_vehicle = UpdateMissionVehicle.Field()
    change_mission_name = ChangeMissionName.Field()
    cancel_mission = CancelMission.Field()
    register_kilometer_at_location = RegisterKilometerAtLocation.Field()


class SignUp(graphene.ObjectType):
    """
    Création de compte
    """

    user = UserSignUp.Field()
    confirm_fc_email = ConfirmFranceConnectEmail.Field()
    activate_email = ActivateEmail.Field()
    company = CompanySignUp.Field()
    companies = CompaniesSignUp.Field()
    redeem_invite = RedeemInvitation.Field()


class ProtectedCompanies(graphene.ObjectType):
    softwareRegistration = CompanySoftwareRegistration.Field()
    syncEmployees = SyncThirdPartyEmployees.Field()


class PrivateAuth(graphene.ObjectType):
    france_connect_login = FranceConnectLogin.Field()
    agent_connect_login = AgentConnectLogin.Field()


class Account(graphene.ObjectType):
    change_email = ChangeEmail.Field()
    change_timezone = ChangeTimezone.Field()
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


class ProtectedMutations(graphene.ObjectType):
    company = graphene.Field(
        ProtectedCompanies, resolver=lambda root, info: ProtectedCompanies()
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

    controller_scan_code = ControllerScanCode.Field()


class Queries(
    UserQuery,
    CheckQuery,
    CompanyQuery,
    MissionQuery,
    BulkActivityQuery,
    graphene.ObjectType,
):
    """
    Requêtes de consultation qui ne modifient pas l'état du système
    """

    pass


class PrivateQueries(
    company.NonPublicQuery,
    GetInvitation,
    UserReadTokenQuery,
    UserOAuthTokenQuery,
    UserOAuthClientQuery,
    ControllerUserQuery,
    graphene.ObjectType,
):
    pass


graphql_schema = graphene.Schema(
    query=Queries, mutation=Mutations, types=[AddressOutput]
)

private_graphql_schema = graphene.Schema(
    query=PrivateQueries, mutation=PrivateMutations, types=[AddressOutput]
)

protected_graphql_schema = graphene.Schema(
    query=None, mutation=ProtectedMutations
)

from app.controllers.contacts import *
