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


class InvalidParamsError(MobilicError):
    code = "INVALID_INPUTS"
    http_status_code = 422


class InternalError(MobilicError):
    code = "INTERNAL_SERVER_ERROR"


class AuthenticationError(MobilicError):
    code = "AUTHENTICATION_ERROR"
    default_should_alert_team = False
    http_status_code = 401


class AuthorizationError(MobilicError):
    code = "AUTHORIZATION_ERROR"
    http_status_code = 403


class SirenAlreadySignedUpError(MobilicError):
    code = "SIREN_ALREADY_SIGNED_UP"
    default_should_alert_team = False


class FranceConnectAuthenticationError(MobilicError):
    code = "FRANCE_CONNECT_ERROR"


class InvalidTokenError(MobilicError):
    code = "INVALID_TOKEN"
    default_should_alert_team = False


class TokenExpiredError(MobilicError):
    code = "EXPIRED_TOKEN"
    default_should_alert_team = False


class EmailAlreadyRegisteredError(MobilicError):
    code = "EMAIL_ALREADY_REGISTERED"
    default_message = "A user is already registered for this email"
    default_should_alert_team = False


class FCUserAlreadyRegisteredError(MobilicError):
    code = "FC_USER_ALREADY_REGISTERED"
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
                        ),
                    )
                )
            )


class MissionAlreadyValidatedByAdminError(MobilicError):
    code = "MISSION_ALREADY_VALIDATED_BY_ADMIN"
    default_message = "A company admin validated the mission activities for the user, no further changes can be made."


class MissionAlreadyValidatedByUserError(MobilicError):
    code = "MISSION_ALREADY_VALIDATED_BY_USER"
    default_message = "The user validated his activities on the mission, only himself or a company admin can edit them."


class MissionStillRunningError(MobilicError):
    code = "MISSION_STILL_RUNNING"
    default_message = "The mission has activities currently running, it cannot be validated yet."


class NoActivitiesToValidateError(MobilicError):
    code = "NO_ACTIVITIES_TO_VALIDATE"


class InvalidResourceError(MobilicError):
    code = "INVALID_RESOURCE"


class ResourceAlreadyDismissedError(InvalidResourceError):
    pass


class DuplicateExpendituresError(MobilicError):
    code = "DUPLICATE_EXPENDITURES"
    default_should_alert_team = False


class MissingPrimaryEmploymentError(MobilicError):
    code = "NO_PRIMARY_EMPLOYMENT"


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
    "activity_start_time_before_end_time": lambda _: InvalidParamsError(
        "End time of activity cannot be before the start time"
    ),
    "activity_version_start_time_before_end_time": lambda _: InvalidParamsError(
        "End time of activity cannot be before the start time"
    ),
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
    "only_one_current_primary_employment_per_user": lambda _: OverlappingEmploymentsError(
        "User cannot have two overlapping primary employments",
        overlap_type="primary",
        should_alert_team=True,
    ),
    "no_simultaneous_employments_for_the_same_company": lambda _: OverlappingEmploymentsError(
        "User cannot have two overlapping employments on the same company",
        overlap_type="company",
        should_alert_team=False,
    ),
    "no_duplicate_expenditures_per_user_and_mission": lambda _: DuplicateExpendituresError(
        "An expenditure of that type is already logged for the user on the mission"
    ),
    "company_siren_key": lambda _: SirenAlreadySignedUpError(
        "SIREN already registered"
    ),
    "user_email_key": lambda _: EmailAlreadyRegisteredError(),
    "user_can_only_end_mission_once": lambda error: MissionAlreadyEndedError(
        mission_end=_get_conflicting_mission_end(error)
    ),
    "unique_registration_numbers_among_company": lambda _: VehicleAlreadyRegisteredError(),
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

    app.logger.exception(
        db_error,
        extra={
            "post_to_mattermost": caught_error is None,
            "log_title": "Unidentified DB Error",
        },
    )
    if caught_error:
        raise caught_error

    raise InternalError("An internal error occurred")
