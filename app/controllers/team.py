import graphene

from app.controllers.event import EventInput
from app.controllers.utils import atomic_transaction
from app.data_access.team_change import TeamChange
from app.domain.permissions import can_submitter_log_on_mission
from app.domain.team import get_or_create_team_mate, enroll_or_release
from app.helpers.authorization import with_authorization_policy
from app.helpers.authentication import current_user
from app.models import Mission


class TeamMateInput(graphene.InputObjectType):
    id = graphene.Int(required=False)
    first_name = graphene.String(required=False)
    last_name = graphene.String(required=False)


class EnrollOrReleaseTeamMate(graphene.Mutation):
    class Arguments(EventInput):
        team_mate = graphene.Argument(TeamMateInput, required=True)
        is_enrollment = graphene.Argument(graphene.Boolean, required=True)
        mission_id = graphene.Argument(graphene.Int, required=True)

    team_change = graphene.Field(TeamChange)

    @classmethod
    @with_authorization_policy(
        can_submitter_log_on_mission,
        get_target_from_args=lambda *args, **kwargs: Mission.query.get(
            kwargs["mission_id"]
        ),
    )
    def mutate(cls, _, info, **enroll_input):
        with atomic_transaction(commit_at_end=True):
            mission = Mission.query.get(enroll_input["mission_id"])
            team_mate = get_or_create_team_mate(
                submitter=current_user,
                team_mate_data=enroll_input.get("team_mate"),
            )
            enroll_or_release(
                current_user,
                mission,
                team_mate,
                enroll_input.get("event_time"),
                is_enrollment=enroll_input["is_enrollment"],
            )

        return EnrollOrReleaseTeamMate(
            team_change={
                "is_enrollment": enroll_input["is_enrollment"],
                "user_time": enroll_input["event_time"],
                "coworker": team_mate,
                "mission_id": mission.id,
            }
        )
