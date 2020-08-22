from flask import g
from functools import wraps
import graphene
from graphene.types.generic import GenericScalar
from graphql import GraphQLError
from abc import ABC, abstractmethod

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
    code = 1


class AuthenticationError(MobilicError):
    code = 100


class AuthorizationError(MobilicError):
    code = 101


class InaccessibleSirenError(MobilicError):
    code = 102


class SirenAlreadySignedUpError(MobilicError):
    code = 103


class UnavailableSirenAPIError(MobilicError):
    code = 104


class NoSirenAPICredentialsError(MobilicError):
    code = 105


class MailjetError(MobilicError):
    code = 106


class FranceConnectAuthenticationError(MobilicError):
    code = 107


class UserDoesNotExistError(MobilicError):
    code = 108


class OverlappingMissionsError(MobilicError):
    code = 200

    def __init__(self, message, user, conflicting_mission, **kwargs):
        super().__init__(message, **kwargs)
        self.extensions.update(
            dict(
                user=dict(
                    id=user.id,
                    firstName=user.first_name,
                    lastName=user.last_name,
                ),
                conflictingMission=dict(
                    id=conflicting_mission.id,
                    eventTime=to_timestamp(conflicting_mission.event_time),
                    submitter=dict(
                        id=conflicting_mission.submitter.id,
                        firstName=conflicting_mission.submitter.first_name,
                        lastName=conflicting_mission.submitter.last_name,
                    ),
                ),
            )
        )


class MissionAlreadyEndedError(MobilicError):
    code = 201

    def __init__(self, message, mission_end, **kwargs):
        super().__init__(message, **kwargs)
        self.extensions.update(
            dict(
                missionEnd=dict(
                    userTime=to_timestamp(mission_end.start_time),
                    submitter=dict(
                        id=mission_end.submitter.id,
                        firstName=mission_end.submitter.first_name,
                        lastName=mission_end.submitter.last_name,
                    ),
                )
            )
        )


class SimultaneousActivitiesError(MobilicError):
    code = 202


class EventAlreadyLoggedError(MobilicError):
    code = 203


class ActivityAlreadyDismissedError(MobilicError):
    code = 204


class NonContiguousActivitySequenceError(MobilicError):
    code = 205


class DuplicateExpenditureError(MobilicError):
    code = 206


class ExpenditureAlreadyDismissedError(MobilicError):
    code = 207


class MissingPrimaryEmploymentError(MobilicError):
    code = 300


class EmploymentAlreadyReviewedByUserError(MobilicError):
    code = 301


class EmploymentNotFoundError(MobilicError):
    code = 302


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
