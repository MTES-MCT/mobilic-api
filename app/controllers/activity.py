from app.controllers.team import TeamMateInput
from app.helpers.authentication import current_user
from sqlalchemy.orm import selectinload
import graphene

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.log_activities import (
    log_group_activity,
    check_activity_sequence_in_mission_and_handle_duplicates,
    resolve_driver,
)
from app.helpers.authentication import AuthorizationError
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import (
    graphene_enum_type,
    DateTimeWithTimeStampSerialization,
)
from app.models import Mission
from app.models.activity import InputableActivityType, Activity, ActivityOutput
from app.models.event import DismissType
from app.models.user import User
from app.controllers.event import EventInput


def _preload_db_resources():
    User.query.options(
        selectinload(User.activities)
        .selectinload(Activity.mission)
        .selectinload(Mission.activities)
        .selectinload(Activity.user)
    ).filter(User.id == current_user.id).one()


class ActivityInput(EventInput):
    type = graphene.Argument(
        graphene_enum_type(InputableActivityType), required=True
    )
    user_time = graphene.Argument(
        DateTimeWithTimeStampSerialization, required=False
    )
    driver = graphene.Argument(TeamMateInput, required=False)
    mission_id = graphene.Int(required=False)
    comment = graphene.String(required=False)


class LogActivity(graphene.Mutation):
    Arguments = ActivityInput

    mission_activities = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **activity_input):
        app.logger.info(
            f"Logging activity submitted by {current_user} of company {current_user.company}"
        )
        with atomic_transaction(commit_at_end=True):
            _preload_db_resources()
            user_time = (
                activity_input.get("user_time") or activity_input["event_time"]
            )
            mission_id = activity_input.get("mission_id")
            if not mission_id:
                mission = current_user.mission_at(user_time)
            else:
                mission = Mission.query.get(mission_id)

            log_group_activity(
                submitter=current_user,
                type=activity_input["type"],
                mission=mission,
                event_time=activity_input["event_time"],
                user_time=user_time,
                driver=resolve_driver(
                    current_user, activity_input.get("driver")
                )
                if activity_input.get("driver")
                else None,
                comment=activity_input.get("comment"),
            )

        return LogActivity(
            mission_activities=mission.activities_for(current_user)
        )


def _get_activities_to_revise_or_cancel(activity_id):
    activity = Activity.query.get(activity_id)

    if (
        current_user.id != activity.submitter_id
        and current_user.id != activity.user_id
    ):
        raise AuthorizationError(
            f"{current_user} cannot cancel {activity} because it is not related to them"
        )

    relevant_events = [activity]
    if current_user.id == activity.submitter_id:
        # Get also events submitted at the same time, which represent the same domain event but for other team mates
        relevant_events = Activity.query.filter(
            Activity.submitter_id == current_user.id,
            Activity.event_time == activity.event_time,
        ).all()

    return [e for e in relevant_events if e.is_acknowledged]


class ActivityEditInput(EventInput):
    activity_id = graphene.Argument(graphene.Int, required=True)
    dismiss = graphene.Boolean(required=True)
    user_time = DateTimeWithTimeStampSerialization(required=False)
    comment = graphene.Argument(graphene.String, required=False)


class EditActivity(graphene.Mutation):
    Arguments = ActivityEditInput

    mission_activities = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **edit_input):
        with atomic_transaction(commit_at_end=True):
            activities_to_update = _get_activities_to_revise_or_cancel(
                edit_input["activity_id"]
            )
            if not activities_to_update:
                raise ValueError(
                    f"Could not find valid Activity events with id {edit_input['activity_id']}"
                )
            mission = None
            for activity in activities_to_update:
                mission = activity.mission
                db.session.add(activity)
                app.logger.info(
                    f"{'Cancelling' if edit_input['dismiss'] else 'Revising'} {activity}"
                )
                if edit_input["dismiss"]:
                    activity.dismiss(
                        DismissType.USER_CANCEL,
                        edit_input["event_time"],
                        edit_input.get("comment"),
                    )
                else:
                    activity.revise(
                        edit_input["event_time"],
                        revision_comment=edit_input.get("comment"),
                        user_time=edit_input.get("user_time"),
                    )
                check_activity_sequence_in_mission_and_handle_duplicates(
                    activity.user, activity.mission, edit_input["event_time"]
                )

        return EditActivity(
            mission_activities=mission.activities_for(current_user)
        )
