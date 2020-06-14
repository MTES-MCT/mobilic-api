from flask import g
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


class AuthenticationError(MobilicError):
    code = 100


class AuthorizationError(MobilicError):
    code = 101


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
                    userTime=to_timestamp(mission_end.user_time),
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


class InvalidEventParamsError(MobilicError):
    code = 203


class ActivityAlreadyDismissedError(MobilicError):
    code = 204


class MutationWithNonBlockingErrors(graphene.Mutation):
    class Meta:
        abstract = True

    non_blocking_errors = graphene.List(
        GenericScalar,
        description="Les erreurs mineures déclenchées par la requête, dont la connaissance peut intéresser l'appelant",
    )

    @classmethod
    def mutate(cls, *args, **kwargs):
        g.non_blocking_errors = []
        output = cls._mutate(*args, **kwargs)
        output.non_blocking_errors = [
            e.to_dict() for e in g.non_blocking_errors
        ]
        return output

    @classmethod
    def _mutate(cls, *args, **kwargs):
        raise NotImplementedError


def add_non_blocking_error(error):
    if not g.get("non_blocking_errors"):
        g.non_blocking_errors = []
    g.non_blocking_errors.append(error)
