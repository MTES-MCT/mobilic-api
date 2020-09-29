from flask import g
from functools import wraps
import graphene
from graphene.types.generic import GenericScalar
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


class ActivitySequenceError(MobilicError):
    code = "ACTIVITY_SEQUENCE_ERROR"


class MissionAlreadyEndedError(ActivitySequenceError):
    def __init__(self, message, mission_end, **kwargs):
        super().__init__(message, **kwargs)
        self.extensions.update(
            dict(
                missionEnd=dict(
                    startTime=to_timestamp(mission_end.start_time),
                    submitter=dict(
                        id=mission_end.submitter.id,
                        firstName=mission_end.submitter.first_name,
                        lastName=mission_end.submitter.last_name,
                    ),
                )
            )
        )


class SimultaneousActivitiesError(ActivitySequenceError):
    def __init__(
        self,
        message="Mission already contains an activity with the same start time for the user",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


class InvalidResourceError(MobilicError):
    code = "INVALID_RESOURCE"


class ResourceAlreadyDismissedError(InvalidResourceError):
    pass


class NonContiguousActivitySequenceError(ActivitySequenceError):
    pass


class DuplicateExpendituresError(MobilicError):
    code = "DUPLICATE_EXPENDITURES"


class MissingPrimaryEmploymentError(MobilicError):
    code = "NO_PRIMARY_EMPLOYMENT"


class OverlappingEmploymentsError(MobilicError):
    code = "OVERLAPPING_EMPLOYMENTS"

    def __init__(self, underlying_error, **kwargs):
        message = "User cannot have two overlapping primary employments or two overlapping employments for the same company"

        overlap_type = None
        if isinstance(underlying_error, IntegrityError):
            pg_error_diag = underlying_error.orig.diag
            violated_constraint_name = pg_error_diag.constraint_name
            if (
                violated_constraint_name
                == "only_one_current_primary_employment_per_user"
            ):
                overlap_type = "primary"
                message = (
                    "User cannot have two overlapping primary employments"
                )
            elif (
                violated_constraint_name
                == "no_simultaneous_employments_for_the_same_company"
            ):
                overlap_type = "company"
                message = "User cannot have two overlapping employments on the same company"

        super().__init__(message, **kwargs)
        if overlap_type:
            self.extensions.update(dict(overlapType=overlap_type))


class MutationWithNonBlockingErrors(graphene.Mutation):
    class Meta:
        abstract = True

    @classmethod
    def mutate_with_non_blocking_errors(cls, mutate):
        @wraps(mutate)
        def mutate_wrapper(*args, **kwargs):
            g.non_blocking_errors = []
            output = mutate(*args, **kwargs)
            output_type = getattr(cls, "Output")
            non_blocking_errors = [e.to_dict() for e in g.non_blocking_errors]
            if output_type:
                return output_type(
                    output=output, non_blocking_errors=non_blocking_errors
                )
            output.non_blocking_errors = non_blocking_errors
            return output

        return mutate_wrapper

    @classmethod
    def __init_subclass_with_meta__(cls, **kwargs):
        output_type = getattr(cls, "Output")
        non_blocking_errors_type = graphene.List(
            GenericScalar,
            description="Les erreurs mineures déclenchées par la requête, dont la connaissance peut intéresser l'appelant",
        )
        if output_type:

            class AugmentedOutput(graphene.ObjectType):
                class Meta:
                    name = cls.__name__ + "Output"

                output = output_type
                non_blocking_errors = non_blocking_errors_type

            setattr(cls, "Output", AugmentedOutput)
        else:
            try:
                if "name" not in kwargs:
                    kwargs["name"] = cls.__name__ + "Output"
            except:
                pass
            setattr(cls, "non_blocking_errors", non_blocking_errors_type)

        setattr(cls, "mutate", cls.mutate_with_non_blocking_errors(cls.mutate))
        super().__init_subclass_with_meta__(**kwargs)


def add_non_blocking_error(error):
    if not g.get("non_blocking_errors"):
        g.non_blocking_errors = []
    g.non_blocking_errors.append(error)
