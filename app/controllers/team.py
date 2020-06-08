import graphene

from app.controllers.event import EventInput
from app.controllers.utils import atomic_transaction
from app.data_access.team_change import TeamChange
from app.domain.permissions import can_submitter_log_on_mission
from app.domain.team import get_or_create_team_mate, enroll_or_release
from app.helpers.authorization import with_authorization_policy
from app.helpers.authentication import current_user
from app.models import Mission
from app.models.activity import ActivityType


class TeamMateInput(graphene.InputObjectType):
    """
    Données d'identification d'un coéquipier
    """

    id = graphene.Int(required=False, description="Identifiant du coéquipier")
    first_name = graphene.String(
        required=False, description="Prénom du coéquipier"
    )
    last_name = graphene.String(
        required=False, description="Nom du coéquipier"
    )


class EnrollOrReleaseTeamMate(graphene.Mutation):
    """
    Ajoute ou retire un coéquipier sur une mission.

    Retourne la liste des évolutions de l'équipe pour la mission
    """

    class Arguments(EventInput):
        team_mate = graphene.Argument(
            TeamMateInput,
            required=True,
            description="Coéquipier à ajouter ou retirer",
        )
        is_enrollment = graphene.Argument(
            graphene.Boolean,
            required=True,
            description="Indique si c'est un ajout ou un retrait",
        )
        mission_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de la mission à laquelle ajouter ou retirer le coéquipier",
        )

    team_changes = graphene.List(TeamChange)

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
            activity = enroll_or_release(
                current_user,
                mission,
                team_mate,
                enroll_input.get("event_time"),
                is_enrollment=enroll_input["is_enrollment"],
            )

        team_change = None
        if activity:
            team_change = {
                "is_enrollment": activity.type != ActivityType.REST,
                "user_time": activity.user_time,
                "coworker": activity.user,
                "mission_id": mission.id,
            }

        return EnrollOrReleaseTeamMate(
            team_changes=[team_change] if team_change else []
        )
