import graphene
from datetime import datetime
from graphene.types.generic import GenericScalar
from sqlalchemy.orm import selectinload

from app import app, db
from app.controllers.utils import atomic_transaction, Void
from app.domain.permissions import can_user_log_on_mission_at
from app.helpers.authentication import current_user
from app.domain.log_activities import log_activity
from app.helpers.errors import (
    AuthorizationError,
    ResourceAlreadyDismissedError,
    InvalidParamsError,
)
from app.helpers.authorization import (
    with_authorization_policy,
    authenticated_and_active,
)
from app.helpers.graphene_types import (
    graphene_enum_type,
    TimeStamp,
)
from app.models import User, Mission
from app.models.activity import Activity, ActivityOutput, ActivityType


class ActivityLogInput:
    type = graphene.Argument(
        graphene_enum_type(ActivityType),
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
        description="Optionnel, horodatage de fin de l'activité. Ne peut être passé que si le mode tachygraphe est désactivé (`switch=False`)",
    )
    switch = graphene.Argument(
        graphene.Boolean,
        required=False,
        description="Optionnel, 'mode tachygraphe'. Dans ce mode l'enregistrement de la nouvelle activité met fin à l'activité en cours. Si l'option n'est pas activée et qu'il existe déjà une activité en cours l'enregistrement déclenchera une erreur. L'option ne peut être activée en même temps qu'une date de fin est spécifiée. Par défaut l'option est activée.",
    )


class LogActivity(graphene.Mutation):
    """
    Enregistrement d'une nouvelle activité.

    Retourne l'activité nouvellement créée.
    """

    Arguments = ActivityLogInput

    Output = ActivityOutput

    @classmethod
    @with_authorization_policy(authenticated_and_active)
    def mutate(cls, _, info, **activity_input):
        with atomic_transaction(commit_at_end=True):
            switch_mode = activity_input.get("switch", True)
            if switch_mode and activity_input.get("end_time"):
                raise InvalidParamsError(
                    "Préciser une date de fin n'est pas autorisé en mode tachygraphe"
                )

            reception_time = datetime.now()
            app.logger.info(
                f"Logging activity {activity_input['type']} submitted by {current_user}"
            )
            mission_id = activity_input.get("mission_id")
            mission = Mission.query.options(
                selectinload(Mission.activities)
            ).get(mission_id)
            user = current_user
            user_id = activity_input.get("user_id")
            if user_id:
                user = User.query.get(user_id)

            start_time = activity_input["start_time"]

            if user and switch_mode and mission:
                current_activity = mission.current_activity_for_at(
                    user, start_time
                )
                if current_activity:
                    if current_activity.type == activity_input.get("type"):
                        return current_activity
                    if not current_activity.end_time:
                        current_activity.revise(
                            reception_time,
                            bypass_check=True,
                            end_time=start_time,
                        )

            activity = log_activity(
                submitter=current_user,
                user=user,
                mission=mission,
                type=activity_input["type"],
                reception_time=reception_time,
                start_time=activity_input["start_time"],
                end_time=activity_input.get("end_time"),
                context=activity_input.get("context"),
            )

        return activity


class ActivityEditInput:
    activity_id = graphene.Argument(
        graphene.Int,
        required=True,
        description="Identifiant de l'activité à modifier.",
    )
    start_time = TimeStamp(
        required=False,
        description="Dans le cas d'une modification de l'heure de début, nouvel horodatage de début de l'activité",
    )
    end_time = TimeStamp(
        required=False,
        description="Dans le cas d'une modification de l'heure de fin, nouvel horodatage de fin de l'activité",
    )
    remove_end_time = graphene.Boolean(
        required=False,
        description="Indique l'annulation de la fin de l'activité. Incompatible avec le passage d'une heure de fin.",
    )
    context = graphene.Argument(
        GenericScalar,
        required=False,
        description="Champ libre sur le contexte de la modification. Utile pour préciser la cause",
    )


def edit_activity(
    activity_id,
    cancel,
    start_time=None,
    end_time=None,
    remove_end_time=False,
    context=None,
):
    with atomic_transaction(commit_at_end=True):
        reception_time = datetime.now()
        activity_to_update = Activity.query.get(activity_id)

        if not activity_to_update:
            raise AuthorizationError(
                f"Actor is not authorized to edit the activity"
            )

        mission = Mission.query.options(selectinload(Mission.activities)).get(
            activity_to_update.mission_id
        )

        if not can_user_log_on_mission_at(
            current_user, mission, activity_to_update.start_time
        ) or (
            start_time
            and not can_user_log_on_mission_at(
                current_user, mission, start_time
            )
        ):
            raise AuthorizationError(
                f"Actor is not authorized to edit the activity"
            )

        if activity_to_update.is_dismissed:
            raise ResourceAlreadyDismissedError(f"Activity already dismissed.")

        db.session.add(activity_to_update)
        app.logger.info(
            f"{'Cancelling' if cancel else 'Revising'} {activity_to_update}"
        )
        if cancel:
            activity_to_update.dismiss(reception_time, context)
        else:
            updates = {}
            if start_time:
                updates["start_time"] = start_time
            if end_time or remove_end_time:
                updates["end_time"] = end_time
            activity_to_update.revise(
                reception_time, revision_context=context, **updates
            )

    return activity_to_update


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

    Output = Void

    @classmethod
    @with_authorization_policy(authenticated_and_active)
    def mutate(cls, _, info, **edit_input):
        edit_activity(
            edit_input["activity_id"],
            cancel=True,
            context=edit_input.get("context"),
        )
        return Void(success=True)


class EditActivity(graphene.Mutation):
    """
    Correction d'une activité précédemment enregistrée.

    Retourne l'activité modifiée.
    """

    Arguments = ActivityEditInput

    Output = ActivityOutput

    @classmethod
    @with_authorization_policy(authenticated_and_active)
    def mutate(cls, _, info, **edit_input):
        if (
            not edit_input.get("start_time")
            and not edit_input.get("end_time")
            and not edit_input.get("remove_end_time")
        ):
            raise InvalidParamsError(
                "At least one of startTime or endTime or removeEndTime should be set"
            )

        if edit_input.get("end_time") and edit_input.get("remove_end_time"):
            raise InvalidParamsError(
                "Either endTime or removeEndTime should be set but not both"
            )

        return edit_activity(
            edit_input["activity_id"],
            cancel=False,
            start_time=edit_input.get("start_time"),
            end_time=edit_input.get("end_time"),
            remove_end_time=edit_input.get("remove_end_time"),
            context=edit_input.get("context"),
        )
