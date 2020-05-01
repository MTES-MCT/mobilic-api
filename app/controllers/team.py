import graphene

from app.controllers.event import EventInput
from app.controllers.utils import atomic_transaction
from app.data_access.user import UserOutput
from app.domain.team import get_or_create_team_mate, enroll_or_release
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.authentication import current_user


class TeamMateInput(graphene.InputObjectType):
    id = graphene.Int(required=False)
    first_name = graphene.String(required=False)
    last_name = graphene.String(required=False)


class EnrollOrReleaseTeamMate(graphene.Mutation):
    class Arguments(EventInput):
        team_mate = graphene.Argument(TeamMateInput, required=True)
        is_enrollment = graphene.Argument(graphene.Boolean, required=True)

    coworker = graphene.Field(UserOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **enroll_input):
        with atomic_transaction(commit_at_end=True):
            team_mate = get_or_create_team_mate(
                submitter=current_user,
                team_mate_data=enroll_input.get("team_mate"),
            )
            enroll_or_release(
                current_user,
                team_mate,
                enroll_input.get("event_time"),
                is_enrollment=enroll_input["is_enrollment"],
            )

        return EnrollOrReleaseTeamMate(coworker=team_mate)
