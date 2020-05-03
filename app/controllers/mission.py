from app.controllers.team import TeamMateInput
from app.data_access.mission import MissionOutput
from app.helpers.authentication import current_user
import graphene
from graphene.types.generic import GenericScalar

from app import app
from app.controllers.utils import atomic_transaction
from app.domain.log_activities import log_group_activity
from app.domain.mission import begin_mission
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import graphene_enum_type
from app.models.activity import InputableActivityType, ActivityType
from app.models.mission import Mission
from app.controllers.event import EventInput


class MissionInput(EventInput):
    name = graphene.Argument(graphene.String, required=False)
    first_activity_type = graphene.Argument(
        graphene_enum_type(InputableActivityType), required=True
    )
    driver = graphene.Argument(TeamMateInput, required=False)
    vehicle_registration_number = graphene.String(required=False)
    vehicle_id = graphene.Int(required=False)
    team = graphene.List(TeamMateInput, required=False)


class BeginMission(graphene.Mutation):
    Arguments = MissionInput

    mission = graphene.Field(MissionOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **mission_input):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Starting a new mission with name {mission_input.get('name')}"
            )
            mission = begin_mission(user=current_user, **mission_input)

        return BeginMission(mission=mission)


class EndMission(graphene.Mutation):
    class Arguments(EventInput):
        mission_id = graphene.Int(required=False)
        expenditures = GenericScalar(required=False)

    mission = graphene.Field(MissionOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **args):
        with atomic_transaction(commit_at_end=True):
            mission_id = args.get("mission_id")
            if not mission_id:
                mission = current_user.mission_at(args.get("event_time"))
            else:
                mission = Mission.query.get(mission_id)

            app.logger.info(f"Ending mission {mission}")
            mission.expenditures = args.get("expenditures")
            log_group_activity(
                submitter=current_user,
                mission=mission,
                type=ActivityType.REST,
                event_time=args["event_time"],
                user_time=args["event_time"],
            )

        return EndMission(mission=mission)
