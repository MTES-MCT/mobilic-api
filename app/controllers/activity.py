from app.domain.permissions import can_submitter_log_on_mission
from app.helpers.authentication import current_user
import graphene
from datetime import datetime
from graphene.types.generic import GenericScalar

from app import app, db
from app.controllers.utils import atomic_transaction
from app.domain.log_activities import (
    log_activity,
    check_activity_sequence_in_mission_and_handle_duplicates,
)
from app.helpers.errors import (
    AuthorizationError,
    ActivityAlreadyDismissedError,
)
from app.helpers.authorization import with_authorization_policy, authenticated
from app.helpers.graphene_types import (
    graphene_enum_type,
    TimeStamp,
)
from app.models.activity import InputableActivityType, Activity, ActivityOutput
from app.models.event import DismissType
from app.models.queries import (
    mission_query_with_activities,
    user_query_with_activities,
)


class ActivityLogInput:
    type = graphene.Argument(
        graphene_enum_type(InputableActivityType),
        required=True,
        description="Nature de l'activité",
    )
    mission_id = graphene.Int(
        required=True,
        description="Identifiant de la mission pour laquelle la nouvelle activité est réalisée",
    )
    user_id = graphene.Int(
        required=False,
        description="Optionnel, identifiant du travailleur concerné par l'activité. Par défaut c'est l'auteur de l'opération.",
    )
    context = GenericScalar(
        required=False,
        description="Un dictionnaire de données additionnelles. Champ libre.",
    )
    start_time = graphene.Argument(
        TimeStamp,
        required=True,
        description="Horodatage du début de l'activité.",
    )
    end_time = graphene.Argument(
        TimeStamp,
        required=False,
        description="Optionnel, horodatage de fin de l'activité.",
    )


class LogActivity(graphene.Mutation):
    """
    Enregistrement d'une nouvelle activité, d'une manière très similaire à un changement d'activité sur un tachygraphe.

    Retourne la liste des activités de la mission.
    """

    Arguments = ActivityLogInput

    Output = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **activity_input):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            app.logger.info(
                f"Logging activity submitted by {current_user} of company {current_user.company}"
            )
            mission_id = activity_input.get("mission_id")
            mission = mission_query_with_activities().get(mission_id)

            user = current_user
            user_id = activity_input.get("user_id")
            if user_id:
                user = user_query_with_activities().get(user_id)

            log_activity(
                submitter=current_user,
                user=user,
                mission=mission,
                type=activity_input["type"],
                reception_time=reception_time,
                start_time=activity_input["start_time"],
                end_time=activity_input.get("end_time"),
                context=activity_input.get("context"),
            )

        return mission.acknowledged_activities


class ActivityEditInput:
    activity_id = graphene.Argument(
        graphene.Int,
        required=True,
        description="Identifiant de l'activité à modifier.",
    )
    start_time = TimeStamp(
        required=False,
        description="Dans le cas d'une édition, nouvel horodatage de début de l'activité",
    )
    end_time = TimeStamp(
        required=False,
        description="Dans le cas d'une édition, nouvel horodatage de fin de l'activité",
    )
    context = graphene.Argument(
        GenericScalar,
        required=False,
        description="Champ libre sur le contexte de la modification. Utile pour préciser la cause",
    )


def edit_activity(
    activity_id, cancel, start_time=None, end_time=None, context=None
):
    with atomic_transaction(commit_at_end=True):
        reception_time = datetime.now()
        activity_to_update = None
        try:
            activity_to_update = Activity.query.get(activity_id)
        except Exception as e:
            pass

        if not activity_to_update or not activity_to_update.is_acknowledged:
            raise ActivityAlreadyDismissedError(
                f"Could not find valid Activity event with id {activity_id}"
            )
        mission = mission_query_with_activities().get(
            activity_to_update.mission_id
        )

        if not can_submitter_log_on_mission(current_user, mission):
            raise AuthorizationError(
                f"The user is not authorized to edit the activity"
            )

        db.session.add(activity_to_update)
        app.logger.info(
            f"{'Cancelling' if cancel else 'Revising'} {activity_to_update}"
        )
        if cancel:
            activity_to_update.dismiss(
                DismissType.USER_CANCEL, reception_time, context
            )
        else:
            activity_to_update.revise(
                reception_time,
                revision_context=context,
                start_time=start_time,
                end_time=end_time,
            )
        check_activity_sequence_in_mission_and_handle_duplicates(
            activity_to_update.user, activity_to_update.mission, reception_time
        )

    return mission.acknowledged_activities


class CancelActivity(graphene.Mutation):
    """
    Annulation d'une activité précédemment enregistrée.

    Retourne la liste des activités de la mission.
    """

    class Arguments:
        activity_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de l'activité à modifier.",
        )
        context = graphene.Argument(
            GenericScalar,
            required=False,
            description="Champ libre sur le contexte de la modification. Utile pour préciser la cause",
        )

    Output = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **edit_input):
        return edit_activity(
            edit_input["activity_id"],
            cancel=True,
            context=edit_input.get("context"),
        )


class EditActivity(graphene.Mutation):
    """
    Correction d'une activité précédemment enregistrée.

    Retourne la liste des activités de la mission.
    """

    Arguments = ActivityEditInput

    Output = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **edit_input):
        return edit_activity(
            edit_input["activity_id"],
            cancel=False,
            start_time=edit_input.get("start_time"),
            end_time=edit_input.get("end_time"),
            context=edit_input.get("context"),
        )
