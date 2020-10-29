from graphql import GraphQLError
from abc import ABC, abstractmethod
from sqlalchemy.exc import IntegrityError

from app.helpers.time import to_timestamp


class MobilicError(GraphQLError, ABC):
    @property
    @abstractmethod
    def code(self):
        pass

    def __init__(self, message, **kwargs):
        base_extensions = dict(code=self.code)
        base_extensions.update(kwargs.pop("extensions", {}))
        super().__init__(message, extensions=base_extensions, **kwargs)

    def to_dict(self):
        return dict(message=self.message, extensions=self.extensions)


class InvalidParamsError(MobilicError):
    code = "INVALID_INPUTS"


class InternalError(MobilicError):
    code = "INTERNAL_ERROR"


class AuthenticationError(MobilicError):
    code = "AUTHENTICATION_ERROR"


class AuthorizationError(MobilicError):
    code = "AUTHORIZATION_ERROR"


class InaccessibleSirenError(MobilicError):
    code = "INACCESSIBLE_SIREN"


class SirenAlreadySignedUpError(MobilicError):
    code = "SIREN_ALREADY_SIGNED_UP"


class UnavailableSirenAPIError(MobilicError):
    code = "UNAVAILABLE_SIREN_API"


class NoSirenAPICredentialsError(MobilicError):
    code = "NO_SIREN_API_CREDENTIALS"


class MailjetError(MobilicError):
    code = "MAILJET_ERROR"


class FranceConnectAuthenticationError(MobilicError):
    code = "FRANCE_CONNECT_ERROR"


class InvalidTokenError(MobilicError):
    code = "INVALID_TOKEN"


class TokenExpiredError(MobilicError):
    code = "EXPIRED_TOKEN"


class EmailAlreadyRegisteredError(MobilicError):
    code = "EMAIL_ALREADY_REGISTERED"

    def __init__(
        self, message="A user is already registered for this email", **kwargs
    ):
        super().__init__(message, **kwargs)


class FCUserAlreadyRegisteredError(MobilicError):
    code = "FC_USER_ALREADY_REGISTERED"


class OverlappingMissionsError(MobilicError):
    code = "OVERLAPPING_MISSIONS"

    def __init__(self, message, conflicting_mission, **kwargs):
        super().__init__(message, **kwargs)
        self.extensions.update(
            dict(
                conflictingMission=dict(
                    id=conflicting_mission.id,
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
    code = "INVALID_SWITCH"

    def __init__(
        self,
        message="Cannot use switch mode because there is a current activity with an end time",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


class OverlappingActivitiesError(MobilicError):
    code = "OVERLAPPING_ACTIVITIES"

    def __init__(
        self,
        message="Activity is overlapping with existing ones for the user",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


class MissionAlreadyEndedError(MobilicError):
    code = "MISSION_ALREADY_ENDED"

    def __init__(
        self, mission_end=None, message="Mission already ended", **kwargs
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


class InvalidResourceError(MobilicError):
    code = "INVALID_RESOURCE"


class ResourceAlreadyDismissedError(InvalidResourceError):
    pass


class DuplicateExpendituresError(MobilicError):
    code = "DUPLICATE_EXPENDITURES"


class MissingPrimaryEmploymentError(MobilicError):
    code = "NO_PRIMARY_EMPLOYMENT"


class OverlappingEmploymentsError(MobilicError):
    code = "OVERLAPPING_EMPLOYMENTS"

    def __init__(self, message, overlap_type, **kwargs):
        super().__init__(message, **kwargs)
        if overlap_type:
            self.extensions.update(dict(overlapType=overlap_type))


CONSTRAINTS_TO_ERRORS_MAP = {
    "no_overlapping_acknowledged_activities": OverlappingActivitiesError(),
    "activity_start_time_before_end_time": InvalidParamsError(
        "End time of activity cannot be before the start time"
    ),
    "activity_version_start_time_before_end_time": InvalidParamsError(
        "End time of activity cannot be before the start time"
    ),
    "activity_version_start_time_before_reception_time": InvalidParamsError(
        "Start time of activity cannot be in the future"
    ),
    "activity_version_end_time_before_reception_time": InvalidParamsError(
        "End time of activity cannot be in the future"
    ),
    "activity_start_time_before_reception_time": InvalidParamsError(
        "Start time of activity cannot be in the future"
    ),
    "activity_end_time_before_update_time": InvalidParamsError(
        "End time of activity cannot be in the future"
    ),
    "only_one_current_primary_enrollment_per_user": OverlappingEmploymentsError(
        "User cannot have two overlapping primary employments",
        overlap_type="primary",
    ),
    "no_simultaneous_enrollments_for_the_same_company": OverlappingEmploymentsError(
        "User cannot have two overlapping employments on the same company",
        overlap_type="company",
    ),
    "no_duplicate_expenditures_per_user_and_mission": DuplicateExpendituresError(
        "An expenditure of that type is already logged for the user on the mission"
    ),
    "company_siren_key": SirenAlreadySignedUpError("SIREN already registered"),
    "user_email_key": EmailAlreadyRegisteredError(),
    "user_can_only_end_mission_once": MissionAlreadyEndedError(),
}


def handle_database_error(db_error):
    from app import app

    app.logger.exception(db_error)
    if isinstance(db_error, IntegrityError):
        if db_error.orig.diag.constraint_name:
            raise CONSTRAINTS_TO_ERRORS_MAP.get(
                db_error.orig.diag.constraint_name,
                InternalError("An internal error occurred"),
            )
    raise InternalError("An internal error occurred")
