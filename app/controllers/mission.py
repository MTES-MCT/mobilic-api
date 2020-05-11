import graphene
from graphene.types.generic import GenericScalar
from datetime import datetime

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.log_activities import log_group_activity
from app.domain.mission import begin_mission
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import graphene_enum_type
from app.models.activity import InputableActivityType, ActivityType
from app.models.mission import Mission
from app.controllers.event import EventInput
from app.models.mission_validation import MissionValidation
from app.controllers.team import TeamMateInput
from app.data_access.mission import MissionOutput
from app.domain.log_comments import log_comment
from app.domain.permissions import can_submitter_log_on_mission
from app.helpers.authentication import current_user


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
        comment = graphene.String(required=False)

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

            comment = args.get("comment")
            if comment:
                log_comment(
                    submitter=current_user,
                    mission=mission,
                    event_time=args["event_time"],
                    content=comment,
                )

        return EndMission(mission=mission)


class ValidateMission(graphene.Mutation):
    class Arguments:
        mission_id = graphene.Int(required=True)

    mission = graphene.Field(MissionOutput)

    @classmethod
    @with_authorization_policy(
        can_submitter_log_on_mission,
        get_target_from_args=lambda *args, **kwargs: Mission.query.get(
            kwargs["mission_id"]
        ),
    )
    def mutate(cls, _, info, mission_id):
        with atomic_transaction(commit_at_end=True):
            mission = Mission.query.get(mission_id)

            db.session.add(
                MissionValidation(
                    submitter=current_user,
                    event_time=datetime.now(),
                    mission=mission,
                )
            )

        return ValidateMission(mission=mission)


class EditMissionExpenditures(graphene.Mutation):
    class Arguments:
        mission_id = graphene.Int(required=False)
        expenditures = GenericScalar(required=True)

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

            mission.expenditures = args["expenditures"]

        return EditMissionExpenditures(mission=mission)
