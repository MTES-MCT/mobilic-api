from flask_jwt_extended import current_user
import graphene

from app import app, db
from app.controllers.cancel import CancelEvents, get_all_associated_events
from app.controllers.event import (
    preload_or_create_relevant_resources_from_events,
)
from app.controllers.utils import atomic_transaction
from app.data_access.activity import ActivityOutput
from app.data_access.signup import CompanyOutput
from app.domain.log_activities import log_group_activity, log_activity
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import (
    graphene_enum_type,
    DateTimeWithTimeStampSerialization,
)
from app.models.activity import InputableActivityTypes, Activity
from app.models.user import User
from app.controllers.event import EventInput


class SingleActivityInput(EventInput):
    type = graphene_enum_type(InputableActivityTypes)(required=True)
    start_time = DateTimeWithTimeStampSerialization(required=False)
    driver_idx = graphene.Int(required=False)
    vehicle_registration_number = graphene.String(required=False)
    mission = graphene.String(required=False)


class ActivityLog(graphene.Mutation):
    class Arguments:
        data = graphene.List(SingleActivityInput, required=True)

    activities = graphene.List(ActivityOutput)
    company = graphene.Field(CompanyOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        app.logger.info(
            f"Logging activities submitted by {current_user} of company {current_user.company}"
        )
        with atomic_transaction(commit_at_end=True):
            events = sorted(data, key=lambda e: e.event_time)
            preload_or_create_relevant_resources_from_events(events)
            for group_activity in events:
                log_group_activity(
                    submitter=current_user,
                    users=[
                        User.query.get(uid) for uid in group_activity.user_ids
                    ],
                    type=group_activity.type,
                    event_time=group_activity.event_time,
                    start_time=group_activity.start_time
                    or group_activity.event_time,
                    driver_idx=group_activity.driver_idx,
                    vehicle_registration_number=group_activity.vehicle_registration_number,
                    mission=group_activity.mission,
                )

        return ActivityLog(
            activities=current_user.acknowledged_deduplicated_activities_with_driver_switch,
            company=current_user.company,
        )


class CancelActivities(CancelEvents):
    model = Activity

    activities = graphene.List(ActivityOutput)

    @classmethod
    def mutate(cls, *args, **kwargs):
        super().mutate(*args, **kwargs)
        return CancelActivities(
            activities=current_user.acknowledged_deduplicated_activities_with_driver_switch
        )


class ActivityRevisionInput(graphene.InputObjectType):
    event_id = graphene.Field(graphene.Int, required=True)
    event_time = graphene.Field(
        DateTimeWithTimeStampSerialization, required=True
    )
    start_time = graphene.Field(
        DateTimeWithTimeStampSerialization, required=True
    )


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
            for event in data:
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
                        new_activity = log_activity(
                            submitter=current_user,
                            user=db_activity.user,
                            type=db_activity.type,
                            event_time=event.event_time,
                            start_time=event.start_time,
                            vehicle_registration_number=db_activity.vehicle_registration_number,
                            mission=db_activity.mission,
                            team=db_activity.team,
                            driver_idx=db_activity.driver_idx,
                            revise_mode=True,
                        )
                        db_activity.set_revision(
                            new_activity, event.event_time
                        )
                        db.session.add(db_activity)

        return ReviseActivities(
            activities=current_user.acknowledged_deduplicated_activities_with_driver_switch
        )
