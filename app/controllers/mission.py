import graphene
from graphene.types.generic import GenericScalar
from datetime import datetime

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.log_activities import log_group_activity
from app.domain.mission import begin_mission
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.errors import MutationWithNonBlockingErrors
from app.helpers.graphene_types import graphene_enum_type
from app.models.activity import InputableActivityType, ActivityType
from app.models.mission import Mission
from app.models import User
from app.controllers.event import EventInput
from app.models.mission_validation import MissionValidation
from app.controllers.team import TeamMateInput
from app.data_access.mission import MissionOutput
from app.domain.log_comments import log_comment
from app.domain.permissions import can_submitter_log_on_mission
from app.helpers.authentication import current_user
from app.models.queries import (
    user_query_with_activities,
    mission_query_with_activities_and_users,
)


class MissionInput(EventInput):
    name = graphene.Argument(
        graphene.String,
        required=False,
        description="Nom optionnel de la mission",
    )
    first_activity_type = graphene.Argument(
        graphene_enum_type(InputableActivityType),
        required=True,
        description="Nature de la première activité",
    )
    driver = graphene.Argument(
        TeamMateInput,
        required=False,
        description="Identitié du conducteur si déplacement",
    )
    vehicle_registration_number = graphene.String(
        required=False,
        description="Numéro d'immatriculation du véhicule utilisé si véhicule non connu (optionnel)",
    )
    vehicle_id = graphene.Int(
        required=False,
        description="Identifiant du véhicule utilisé, si déjà connu (optionnel)",
    )
    team = graphene.List(
        TeamMateInput,
        required=False,
        description="Liste des coéquipiers sur la mission",
    )


class BeginMission(MutationWithNonBlockingErrors):
    """
    Démarrage d'une nouvelle mission et enregistrement de la première activité.

    Retourne la mission nouvellement créée
    """

    Arguments = MissionInput

    Output = graphene.Field(MissionOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **mission_input):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Starting a new mission with name {mission_input.get('name')}"
            )
            # Preload resources
            user_ids_to_preload = [current_user.id]
            team = mission_input.get("team")
            if team:
                for tm in team:
                    if tm.get("id"):
                        user_ids_to_preload.append(tm.get("id"))
            user_query_with_activities().filter(
                User.id.in_(user_ids_to_preload)
            ).all()

            mission = begin_mission(user=current_user, **mission_input)

        return mission


class EndMission(graphene.Mutation):
    """
    Fin de la mission et enregistrement des frais associés.

    Retourne la mission.
    """

    class Arguments(EventInput):
        mission_id = graphene.Int(
            required=True, description="Identifiant de la mission à terminer"
        )
        expenditures = GenericScalar(
            required=False, description="Frais de la mission"
        )
        comment = graphene.String(
            required=False, description="Commentaire libre sur la mission"
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **args):
        with atomic_transaction(commit_at_end=True):
            mission = mission_query_with_activities_and_users().get(
                args.get("mission_id")
            )

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

        return mission


class ValidateMission(graphene.Mutation):
    """
    Validation du contenu de la mission.

    Retourne la mission.
    """

    class Arguments:
        mission_id = graphene.Int(
            required=True, description="Identifiant de la mission à valider"
        )

    Output = MissionOutput

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

        return mission


class EditMissionExpenditures(graphene.Mutation):
    """
    Correction des frais de la mission.

    Retourne la mission.
    """

    class Arguments:
        mission_id = graphene.Int(
            required=True, description="Identifiant de la mission considérée"
        )
        expenditures = GenericScalar(
            required=True, description="Les frais corrigés"
        )

    Output = MissionOutput

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **args):
        with atomic_transaction(commit_at_end=True):
            mission = Mission.query.get(args.get("mission_id"))

            mission.expenditures = args["expenditures"]

        return mission
