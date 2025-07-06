from graphql import GraphQLError
from abc import ABC, abstractmethod
from sqlalchemy.exc import IntegrityError
import re

from app.helpers.time import to_timestamp


class MobilicError(GraphQLError, ABC):
    @property
    @abstractmethod
    def code(self):
        pass

    http_status_code = 500

    default_should_alert_team = True
    default_message = "Error"

    def __init__(self, message=None, should_alert_team=None, **kwargs):
        if message is None:
            message = self.default_message
        self.should_alert_team = (
            should_alert_team
            if should_alert_team is not None
            else self.default_should_alert_team
        )
        base_extensions = dict(code=self.code)
        base_extensions.update(kwargs.pop("extensions", {}))
        super().__init__(message, extensions=base_extensions, **kwargs)

    def to_dict(self):
        return dict(message=self.message, extensions=self.extensions)


class BadRequestError(MobilicError):
    code = "BAD_REQUEST"
    default_message = "Invalid request"
    http_status_code = 400


class BadGraphQLRequestError(MobilicError):
    code = "BAD_GRAPHQL_REQUEST"
    default_message = "Invalid GraphQL request"
    http_status_code = 400


class InvalidParamsError(MobilicError):
    code = "INVALID_INPUTS"
    http_status_code = 422


class InternalError(MobilicError):
    code = "INTERNAL_SERVER_ERROR"


class AuthenticationError(MobilicError):
    code = "AUTHENTICATION_ERROR"
    default_should_alert_team = False
    http_status_code = 401


class BlockedAccountError(MobilicError):
    code = "BLOCKED_ACCOUNT_ERROR"
    default_should_alert_team = False
    http_status_code = 401


class BadPasswordError(MobilicError):
    code = "BAD_PASSWORD_ERROR"

    def __init__(
        self,
        message,
        nb_bad_tries,
        max_possible_tries,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.extensions.update(
            dict(
                nb_bad_tries=nb_bad_tries,
                max_possible_tries=max_possible_tries,
            )
        )

    default_should_alert_team = False
    http_status_code = 401


class AuthorizationError(MobilicError):
    code = "AUTHORIZATION_ERROR"
    http_status_code = 403


class SiretAlreadySignedUpError(MobilicError):
    code = "SIRET_ALREADY_SIGNED_UP"
    default_should_alert_team = False


class SirenAlreadySignedUpError(MobilicError):
    code = "SIREN_ALREADY_SIGNED_UP"
    default_message = "SIREN already registered"
    default_should_alert_team = False


class CompanyCeasedActivityError(MobilicError):
    code = "COMPANY_HAS_CEASED_ACTIVITY"
    default_message = "Company has ceased activity"
    default_should_alert_team = False


class FranceConnectAuthenticationError(MobilicError):
    code = "FRANCE_CONNECT_ERROR"


class AgentConnectAuthenticationError(MobilicError):
    code = "AGENT_CONNECT_ERROR"


class AgentConnectOrganizationalUnitError(MobilicError):
    code = "AGENT_CONNECT_ORGANIZATIONAL_UNIT_NOT_FOUND_ERROR"


class InvalidTokenError(MobilicError):
    code = "INVALID_TOKEN"
    default_should_alert_team = False


class TokenExpiredError(MobilicError):
    code = "EXPIRED_TOKEN"
    default_should_alert_team = False


class EmailAlreadyRegisteredError(MobilicError):
    code = "ERROR_WHILE_REGISTERING_USER"
    default_message = "An error occurred while registering user"
    default_should_alert_team = False


class ActivationEmailDelayError(MobilicError):
    code = "ACTIVATION_EMAIL_DELAY_ERROR"
    default_message = "An activation email has already been sent"
    default_should_alert_team = False


class FCUserAlreadyRegisteredError(MobilicError):
    code = "FC_USER_ALREADY_REGISTERED"
    default_should_alert_team = False


class EmploymentLinkNotFound(MobilicError):
    code = "EMPLOYMENT_CLIENT_LINK_NOT_FOUND"
    default_should_alert_team = False


class CompanyLinkNotFound(MobilicError):
    code = "COMPANY_CLIENT_LINK_NOT_FOUND"
    default_should_alert_team = False


class EmploymentLinkAlreadyAccepted(MobilicError):
    code = "EMPLOYMENT_CLIENT_LINK_ALREADY_ACCEPTED"
    default_should_alert_team = False


class EmploymentLinkExpired(MobilicError):
    code = "EMPLOYMENT_CLIENT_LINK_EXPIRED"
    default_should_alert_team = False


class OverlappingMissionsError(MobilicError):
    code = "OVERLAPPING_MISSIONS"

    def __init__(self, message, conflicting_mission, **kwargs):
        super().__init__(message, **kwargs)
        self.extensions.update(
            dict(
                conflictingMission=dict(
                    id=conflicting_mission.id,
                    name=conflicting_mission.name,
                    receptionTime=to_timestamp(
                        conflicting_mission.reception_time
                    ),
                    submitter=dict(
                        id=conflicting_mission.submitter.id,
                        firstName=conflicting_mission.submitter.first_name,
                        lastName=conflicting_mission.submitter.last_name,
                    ),
                ),
            )
        )


class UnavailableSwitchModeError(MobilicError):
    code = "INVALID_ACTIVITY_SWITCH"
    default_message = "Invalid time for switch mode because there is a current activity with an end time"


class EmptyActivityDurationError(MobilicError):
    code = "EMPTY_ACTIVITY_DURATION"
    default_message = (
        "End time of activity should be strictly after start time"
    )


class ActivityOutsideEmploymentByEmployeeError(MobilicError):
    code = "ACTIVITY_OUTSIDE_EMPLOYMENT_EMPLOYEE"
    default_message = "Activity can't be added outside employment period"


class ActivityOutsideEmploymentByAdminError(MobilicError):
    code = "ACTIVITY_OUTSIDE_EMPLOYMENT_ADMIN"
    default_message = "Activity can't be added outside employment period"


class UserNotEmployedByCompanyAnymoreEmployeeError(MobilicError):
    code = "USER_NOT_EMPLOYED_BY_COMPANY_ANYMORE_EMPLOYEE"


class UserNotEmployedByCompanyAnymoreAdminError(MobilicError):
    code = "USER_NOT_EMPLOYED_BY_COMPANY_ANYMORE_ADMIN"


class ActivityInFutureError(MobilicError):
    code = "ACTIVITY_TIME_IN_FUTURE"

    def __init__(
        self,
        event_time,
        reception_time,
        event_name,
        message="You can not record activity in the future.",
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.extensions.update(
            dict(
                eventTime=to_timestamp(event_time),
                receptionTime=to_timestamp(reception_time),
                eventName=event_name,
            )
        )


class OverlappingActivitiesError(MobilicError):
    code = "OVERLAPPING_ACTIVITIES"
    default_should_alert_team = False

    def __init__(
        self,
        message="Activity is overlapping with existing ones for the user",
        conflicting_activity=None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        if conflicting_activity:
            self.extensions.update(
                dict(
                    conflictingActivity=dict(
                        id=conflicting_activity.id,
                        startTime=to_timestamp(
                            conflicting_activity.start_time
                        ),
                        endTime=to_timestamp(conflicting_activity.end_time)
                        if conflicting_activity.end_time
                        else None,
                        missionId=conflicting_activity.mission_id,
                        type=conflicting_activity.type.value,
                        submitter=dict(
                            id=conflicting_activity.submitter.id,
                            firstName=conflicting_activity.submitter.first_name,
                            lastName=conflicting_activity.submitter.last_name,
                        ),
                    )
                )
            )


class LogHolidayInNotEmptyMissionError(MobilicError):
    code = "LOG_HOLIDAY_IN_MISSION_NOT_EMPTY"
    default_message = "A holiday or time off should not be logged in a mission which is not empty."


class LogActivityInHolidayMissionError(MobilicError):
    code = "LOG_ACTIVITY_IN_HOLIDAY_MISSION"
    default_message = "An activity should not be logged in a mission representing a holiday or time off."


class MissionAlreadyEndedError(MobilicError):
    code = "MISSION_ALREADY_ENDED"

    def __init__(
        self, message="Mission already ended", mission_end=None, **kwargs
    ):
        super().__init__(message, **kwargs)
        if mission_end:
            self.extensions.update(
                dict(
                    missionEnd=dict(
                        endTime=to_timestamp(mission_end.reception_time),
                        submitter=dict(
                            id=mission_end.submitter.id,
                            firstName=mission_end.submitter.first_name,
                            lastName=mission_end.submitter.last_name,
                        )
                        if mission_end.submitter is not None
                        else dict(),
                    )
                )
            )


class MissionAlreadyValidatedByAdminError(MobilicError):
    code = "MISSION_ALREADY_VALIDATED_BY_ADMIN"
    default_message = "A company admin validated the mission activities for the user, no further changes can be made."


class MissingJustificationForAdminValidation(MobilicError):
    code = "MISSING_JUSTIFICATION_FOR_ADMIN_VALIDATION"
    default_message = "A company admin tried to validate after auto validation without a justification."


class ExpenditureDateNotIncludedInMissionRangeError(MobilicError):
    code = "EXPENDITURE_DATE_NOT_INCLUDED_IN_MISSION_RANGE"
    default_message = "The spending date of the expenditure is not between the start date and the end date of the mission."


class MissionAlreadyValidatedByUserError(MobilicError):
    code = "MISSION_ALREADY_VALIDATED_BY_USER"
    default_message = "The user validated his activities on the mission, only a company admin can edit them."


class MissionNotAlreadyValidatedByUserError(MobilicError):
    code = "MISSION_NOT_ALREADY_VALIDATED_BY_USER"
    default_message = "The user did not validate his activities on the mission, a company admin can not edit them."


class MissionStillRunningError(MobilicError):
    code = "MISSION_STILL_RUNNING"
    default_message = "The mission has activities currently running, it cannot be validated yet."


class UserSelfChangeRoleError(MobilicError):
    code = "USER_SELF_CHANGE_ROLE"
    default_message = "A user can not change its own role, it has to be done by another admin."


class UserSelfTerminateEmploymentError(MobilicError):
    code = "USER_SELF_TERMINATE_EMPLOYMENT"
    default_message = "A user can not terminate its own employment, it has to be done by another admin."


class NoActivitiesToValidateError(MobilicError):
    code = "NO_ACTIVITIES_TO_VALIDATE"


class InvalidResourceError(MobilicError):
    code = "INVALID_RESOURCE"


class EmploymentAlreadyTerminated(MobilicError):
    code = "EMPLOYMENT_ALREADY_TERMINATED"


class ActivityExistAfterEmploymentEndDate(MobilicError):
    code = "ACTIVITY_EXIST_AFTER_EMPLOYMENT_END_DATE"


class ResourceAlreadyDismissedError(InvalidResourceError):
    pass


class DuplicateExpendituresError(MobilicError):
    code = "DUPLICATE_EXPENDITURES"
    default_should_alert_team = False


class InvalidControlToken(MobilicError):
    code = "INVALID_CONTROL_TOKEN"
    default_message = "The Control QR Code can not be read"


class ControlNotFound(MobilicError):
    code = "CONTROL_NOT_FOUND"
    http_status_code = 404


class OverlappingEmploymentsError(MobilicError):
    code = "OVERLAPPING_EMPLOYMENTS"

    def __init__(self, message, overlap_type, **kwargs):
        super().__init__(message, **kwargs)
        if overlap_type:
            self.extensions.update(dict(overlapType=overlap_type))


class VehicleAlreadyRegisteredError(MobilicError):
    code = "VEHICLE_ALREADY_REGISTERED"
    default_message = "Vehicle registration number already exists"
    default_should_alert_team = False


class MissionLocationAlreadySetError(MobilicError):
    code = "LOCATION_ALREADY_SET"
    default_message = (
        "A location of this type has already been set for the mission"
    )
    default_should_alert_team = False


class CompanyAddressAlreadyRegisteredError(MobilicError):
    code = "COMPANY_ADDRESS_ALREADY_REGISTERED"
    default_message = "The address already exists"
    default_should_alert_team = False


CONFLICTING_ROW_ID_RE = re.compile(r", (\d+)\)\.$")


def _parse_conflicting_row_id_from_psql_error_message(error):
    # This is a hack to retrieve the conflicting row in an exclude constraint
    # We parse the message detail of the PSQL error to get the conflicting row id
    message_detail = error.diag.message_detail
    id_regexp_match = CONFLICTING_ROW_ID_RE.search(message_detail)
    return int(id_regexp_match.group(1)) if id_regexp_match else None


def _get_conflicting_entity(error, model):
    conflicting_row_id = _parse_conflicting_row_id_from_psql_error_message(
        error
    )
    return model.query.get(conflicting_row_id) if conflicting_row_id else None


def _get_conflicting_activity(error):
    from app.models import Activity

    return _get_conflicting_entity(error, Activity)


def _get_conflicting_mission_end(error):
    from app.models import MissionEnd

    return _get_conflicting_entity(error, MissionEnd)


# Map violations of db-level constraints to app-level exceptions
CONSTRAINTS_TO_ERRORS_MAP = {
    "no_overlapping_acknowledged_activities": lambda error: OverlappingActivitiesError(
        conflicting_activity=_get_conflicting_activity(error)
    ),
    "activity_start_time_before_end_time": lambda _: EmptyActivityDurationError(),
    "activity_version_start_time_before_end_time": lambda _: EmptyActivityDurationError(),
    "activity_version_start_time_before_reception_time": lambda _: InvalidParamsError(
        "Start time of activity cannot be in the future"
    ),
    "activity_version_end_time_before_reception_time": lambda _: InvalidParamsError(
        "End time of activity cannot be in the future"
    ),
    "activity_start_time_before_reception_time": lambda _: InvalidParamsError(
        "Start time of activity cannot be in the future"
    ),
    "activity_end_time_before_update_time": lambda _: InvalidParamsError(
        "End time of activity cannot be in the future"
    ),
    "no_simultaneous_employments_for_the_same_company": lambda _: OverlappingEmploymentsError(
        "User cannot have two overlapping employments on the same company",
        overlap_type="company",
        should_alert_team=False,
    ),
    "no_duplicate_expenditures_per_user_and_date_and_mission": lambda _: DuplicateExpendituresError(
        "An expenditure of that type and that date is already logged for the user on the mission"
    ),
    "only_one_company_per_siret": lambda _: SiretAlreadySignedUpError(
        "SIRET already registered"
    ),
    "user_email_key": lambda _: EmailAlreadyRegisteredError(),
    "user_can_only_end_mission_once": lambda error: MissionAlreadyEndedError(
        mission_end=_get_conflicting_mission_end(error)
    ),
    "unique_registration_numbers_among_company": lambda _: VehicleAlreadyRegisteredError(),
    "only_one_entry_per_company_and_address": lambda _: CompanyAddressAlreadyRegisteredError(),
}


def handle_database_error(db_error):
    from app import app

    caught_error = None
    if isinstance(db_error, IntegrityError):
        if db_error.orig.diag.constraint_name:
            error_generator = CONSTRAINTS_TO_ERRORS_MAP.get(
                db_error.orig.diag.constraint_name
            )
            if error_generator:
                caught_error = error_generator(db_error.orig)

    app.logger.exception(db_error)
    if caught_error:
        raise caught_error

    raise InternalError("An internal error occurred")
