from flask_jwt_extended import current_user
import graphene

from app import app
from app.controllers.event import preload_relevant_resources_for_event_logging
from app.controllers.utils import atomic_transaction
from app.domain.log_missions import log_mission
from app.helpers.authorization import with_authorization_policy, authenticated
from app.models.mission import MissionOutput
from app.models.user import User
from app.controllers.event import EventInput


class MissionInput(EventInput):
    name = graphene.Field(graphene.String)


class MissionLog(graphene.Mutation):
    class Arguments:
        data = graphene.List(MissionInput, required=True)

    missions = graphene.List(MissionOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Logging missions submitted by {current_user} of company {current_user.company}"
            )
            events = sorted(data, key=lambda e: e.event_time)
            preload_relevant_resources_for_event_logging(
                User.submitted_missions
            )
            for mission in events:
                log_mission(
                    submitter=current_user,
                    start_time=mission.event_time,
                    event_time=mission.event_time,
                    name=mission.name,
                )

        return MissionInput(missions=current_user.missions)
