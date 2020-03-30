from datetime import datetime
from flask_jwt_extended import current_user
import graphene

from app import app
from app.controllers.cancel import CancelEvents, get_all_associated_events
from app.controllers.event import preload_relevant_resources_for_event_logging
from app.controllers.utils import atomic_transaction
from app.data_access.user import UserOutput
from app.domain.log_activities import (
    log_group_activity,
    check_and_fix_neighbour_inconsistencies,
)
from app.domain.log_missions import log_mission
from app.domain.log_vehicle_booking import log_vehicle_booking
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import (
    graphene_enum_type,
    DateTimeWithTimeStampSerialization,
)
from app.models.activity import InputableActivityType, Activity, ActivityOutput
from app.models.user import User
from app.controllers.event import EventInput


class SingleActivityInput(EventInput):
    type = graphene_enum_type(InputableActivityType)(required=True)
    user_time = DateTimeWithTimeStampSerialization(required=False)
    driver_id = graphene.Int(required=False)
    vehicle_registration_number = graphene.String(required=False)
    vehicle_id = graphene.Int(required=False)
    mission = graphene.String(required=False)
    comment = graphene.String(required=False)


class ActivityLog(graphene.Mutation):
    class Arguments:
        data = graphene.List(SingleActivityInput, required=True)

    user = graphene.Field(UserOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        app.logger.info(
            f"Logging activities submitted by {current_user} of company {current_user.company}"
        )
        with atomic_transaction(commit_at_end=True):
            events = sorted(data, key=lambda e: e.event_time)
            preload_relevant_resources_for_event_logging(User.activities)
            for group_activity in events:
                user_time = (
                    group_activity.user_time or group_activity.event_time
                )
                if group_activity.mission:
                    log_mission(
                        name=group_activity.mission,
                        user_time=user_time,
                        event_time=group_activity.event_time,
                        submitter=current_user,
                    )
                if (
                    group_activity.vehicle_registration_number
                    or group_activity.vehicle_id
                ):
                    log_vehicle_booking(
                        vehicle_id=group_activity.vehicle_id,
                        registration_number=group_activity.vehicle_registration_number,
                        user_time=user_time,
                        event_time=group_activity.event_time,
                        submitter=current_user,
                    )
                log_group_activity(
                    submitter=current_user,
                    users=[current_user]
                    + current_user.acknowledged_team_at(user_time),
                    type=group_activity.type,
                    event_time=group_activity.event_time,
                    user_time=user_time,
                    driver=User.query.get(group_activity.driver_id)
                    if group_activity.driver_id
                    else None,
                    comment=group_activity.comment,
                )

        return ActivityLog(user=User.query.get(current_user.id))


class CancelActivities(CancelEvents):
    model = Activity

    activities = graphene.List(ActivityOutput)

    @classmethod
    def mutate(cls, *args, **kwargs):
        super().mutate(*args, **kwargs)
        return CancelActivities(
            activities=current_user.acknowledged_activities
        )


class ActivityRevisionInput(graphene.InputObjectType):
    event_id = graphene.Field(graphene.Int, required=True)
    event_time = graphene.Field(
        DateTimeWithTimeStampSerialization, required=True
    )
    user_time = graphene.Field(
        DateTimeWithTimeStampSerialization, required=True
    )
    comment = graphene.Field(graphene.String, required=False)


class ReviseActivities(graphene.Mutation):
    model = Activity

    class Arguments:
        data = graphene.List(ActivityRevisionInput, required=True)

    activities = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            all_relevant_activities = get_all_associated_events(
                cls.model, [e.event_id for e in data]
            )
            for event in sorted(data, key=lambda e: e.event_time):
                matched_activity = all_relevant_activities.get(event.event_id)
                if not matched_activity:
                    app.logger.warn(
                        f"Could not find {cls.model} events with id {event.event_id} to revise"
                    )
                else:
                    activities_to_revise = [matched_activity]
                    if matched_activity.submitter_id == current_user.id:
                        activities_to_revise = [
                            a
                            for a in all_relevant_activities.values()
                            if a.submitter_id == current_user.id
                            and a.event_time == matched_activity.event_time
                        ]
                    for db_activity in activities_to_revise:
                        app.logger.info(f"Revising {db_activity}")
                        new_activity = db_activity.revise(
                            event.event_time,
                            revision_comment=event.comment,
                            user_time=event.user_time,
                        )
                        if new_activity:
                            revised_activity_neighbours = (
                                new_activity.previous_and_next_acknowledged_activities
                            )
                            neighbours_to_check = {
                                (revised_activity_neighbours[0], new_activity),
                                (new_activity, revised_activity_neighbours[1]),
                                db_activity.previous_and_next_acknowledged_activities,
                            }
                            neighbours_to_check_in_historical_order = sorted(
                                list(neighbours_to_check),
                                key=lambda prev_next: prev_next[0].user_time
                                if prev_next[0]
                                else datetime.fromtimestamp(0),
                            )
                            for (
                                prev,
                                next,
                            ) in neighbours_to_check_in_historical_order:
                                check_and_fix_neighbour_inconsistencies(
                                    prev, next, event.event_time
                                )

        return ReviseActivities(
            activities=current_user.acknowledged_activities
        )
