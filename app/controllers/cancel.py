import graphene
from flask_jwt_extended import current_user
from graphql import GraphQLError

from app import app, db
from app.controllers.utils import atomic_transaction
from app.helpers.authorization import authenticated, with_authorization_policy
from app.helpers.graphene_types import DateTimeWithTimeStampSerialization


class CancelEventInput(graphene.InputObjectType):
    event_id = graphene.Field(graphene.Int, required=True)
    cancel_time = graphene.Field(
        DateTimeWithTimeStampSerialization, required=True
    )


class CancelEvents(graphene.Mutation):
    model = None

    class Arguments:
        data = graphene.List(CancelEventInput, required=True)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            all_events_in_db = cls.model.query.filter(
                cls.model.id.in_([e.event_id for e in data])
            ).all()

            if not all(
                [
                    e.submitter_id == current_user.id
                    or e.user_id == current_user.id
                    for e in all_events_in_db
                ]
            ):
                raise GraphQLError("Unauthorized")

            for event in data:
                event_matches = [
                    e for e in all_events_in_db if e.id == event.event_id
                ]
                if not event_matches:
                    app.logger.warn(
                        f"Could not find {cls.model} events with id {event.event_id} to cancel"
                    )
                else:
                    event_to_cancel = event_matches[0]
                    app.logger.info(f"Cancelling {event_to_cancel}")
                    event_to_cancel.cancelled_at = event.cancel_time
                    db.session.add(event_to_cancel)
