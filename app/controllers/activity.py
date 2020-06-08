from app.controllers.team import TeamMateInput
from app.helpers.authentication import current_user
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
from app.models.queries import mission_query_with_activities_and_users
from app.controllers.event import EventInput


class ActivityInput(EventInput):
    type = graphene.Argument(
        graphene_enum_type(InputableActivityType),
        required=True,
        description="Nature de l'activité",
    )
    user_time = graphene.Argument(
        DateTimeWithTimeStampSerialization,
        required=False,
        description="Horodatage optionnel du début de l'activité. Ne sert que pour les enregistrements en décalé ; dans le fonctionnement en \"temps réel\" c'est l'horodatage de l'évènement qui est utilisé",
    )
    user_end_time = graphene.Argument(
        DateTimeWithTimeStampSerialization,
        required=False,
        description="Horodatage optionnel de la fin de l'activité. Dans le fonctionnement en \"temps réel\" ce champ n'est pas pris en compte",
    )
    driver = graphene.Argument(
        TeamMateInput,
        required=False,
        description="Identité du conducteur si déplacement",
    )
    mission_id = graphene.Int(
        required=True,
        description="Identifiant de la mission pour laquelle la nouvelle activité est réalisée",
    )
    comment = graphene.String(
        required=False,
        description="Commentaire sur l'enregistrement de la nouvelle activité. Utile pour préciser la cause d'un enregistrement a posteriori",
    )


class LogActivity(graphene.Mutation):
    """
    Enregistrement d'une nouvelle activité, d'une manière très similaire à un changement d'activité sur un tachygraphe.

    Retourne la liste des activités de la mission.
    """

    Arguments = ActivityInput

    mission_activities = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **activity_input):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Logging activity submitted by {current_user} of company {current_user.company}"
            )
            user_time = (
                activity_input.get("user_time") or activity_input["event_time"]
            )
            mission_id = activity_input.get("mission_id")
            mission = mission_query_with_activities_and_users().get(mission_id)

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
                user_end_time=activity_input.get("user_end_time"),
            )

        return LogActivity(
            mission_activities=mission.activities_for(current_user)
        )


def _get_activities_to_revise_or_cancel(activity_id, activity_user_time):
    if activity_id:
        activity = Activity.query.get(activity_id)
    else:
        activity = Activity.query.filter(
            Activity.user_id == current_user.id,
            Activity.user_time == activity_user_time,
            Activity.dismissed_at == None,
            Activity.revised_by_id == None,
        ).one()

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
            Activity.user_time == activity.user_time,
        ).all()

    return [e for e in relevant_events if e.is_acknowledged]


class ActivityEditInput(EventInput):
    activity_id = graphene.Argument(
        graphene.Int,
        required=False,
        description="Identifiant de l'activité à modifier. Optionnel en mode offline car l'information n'est pas forcément accessible au moment de la correction",
    )
    activity_user_time = DateTimeWithTimeStampSerialization(
        required=False,
        description="Ancien horodatage de début de l'activité à modifier. Ne sert que dans le mode offline pour retrouver l'activité si son identifiant n'est pas communiqué",
    )
    dismiss = graphene.Boolean(
        required=True,
        description="Indique si l'activité doit être supprimée ou simplement éditée",
    )
    user_time = DateTimeWithTimeStampSerialization(
        required=False,
        description="Dans le cas d'une édition, nouvel horodatage de début de l'activité",
    )
    comment = graphene.Argument(
        graphene.String,
        required=False,
        description="Commentaire libre sur le contexte de la modification. Utile pour préciser la cause",
    )
    user_end_time = DateTimeWithTimeStampSerialization(
        required=False,
        description="Dans le cas d'une édition, nouvel horodatage de fin de l'activité",
    )


class EditActivity(graphene.Mutation):
    """
    Correction d'une activité précédemment enregistrée.

    Retourne la liste des activités de la mission.
    """

    Arguments = ActivityEditInput

    mission_activities = graphene.List(ActivityOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **edit_input):
        with atomic_transaction(commit_at_end=True):
            activities_to_update = []
            try:
                activities_to_update = _get_activities_to_revise_or_cancel(
                    edit_input.get("activity_id"),
                    edit_input.get("activity_user_time"),
                )
            except Exception as e:
                pass

            if not activities_to_update:
                raise ValueError(
                    f"Could not find valid Activity events with id {edit_input.get('activity_id')}, time {edit_input.get('activity_user_time')}"
                )
            mission = mission_query_with_activities_and_users().get(
                activities_to_update[0].mission_id
            )
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
                        user_end_time=edit_input.get("user_end_time"),
                    )
                check_activity_sequence_in_mission_and_handle_duplicates(
                    activity.user, activity.mission, edit_input["event_time"]
                )

        return EditActivity(
            mission_activities=mission.activities_for(current_user)
        )
