import graphene
from flask_jwt_extended import current_user
from graphql import GraphQLError

from app import app, db
from app.controllers.utils import atomic_transaction
from app.helpers.authorization import authenticated, with_authorization_policy
from app.helpers.graphene_types import DateTimeWithTimeStampSerialization


def get_all_associated_events(model, event_ids):
    base_events_in_db = model.query.filter(
        model.id.in_([eid for eid in event_ids])
    ).all()

    if not all(
        [
            e.submitter_id == current_user.id or e.user_id == current_user.id
            for e in base_events_in_db
        ]
    ):
        raise GraphQLError("Unauthorized")

    secondary_events_in_db = model.query.filter(
        model.submitter_id == current_user.id,
        model.event_time.in_([e.event_time for e in base_events_in_db]),
    ).all()

    filtered_secondary_events_in_db = [
        e for e in secondary_events_in_db if e.is_acknowledged
    ]

    return {
        e.id: e for e in base_events_in_db + filtered_secondary_events_in_db
    }


class CancelEventInput(graphene.InputObjectType):
    event_id = graphene.Field(graphene.Int, required=True)
    cancel_time = graphene.Field(
        DateTimeWithTimeStampSerialization, required=True
    )


class CancelEvents(graphene.Mutation):
    class Arguments:
        data = graphene.List(CancelEventInput, required=True)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            all_relevant_events = get_all_associated_events(
                cls.model, [e.event_id for e in data]
            )
            for event in data:
                matched_event = all_relevant_events.get(event.event_id)
                if not matched_event:
                    app.logger.warn(
                        f"Could not find {cls.model} events with id {event.event_id} to cancel"
                    )
                else:
                    events_to_cancel = [matched_event]
                    if matched_event.submitter_id == current_user.id:
                        events_to_cancel = [
                            e
                            for e in all_relevant_events.values()
                            if e.submitter_id == current_user.id
                            and e.event_time == matched_event.event_time
                        ]
                    for db_event in events_to_cancel:
                        app.logger.info(f"Cancelling {db_event}")
                        db_event.cancelled_at = event.cancel_time
                        db.session.add(db_event)
