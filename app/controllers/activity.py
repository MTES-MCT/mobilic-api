from datetime import datetime

import graphene
from graphene.types.generic import GenericScalar
from sqlalchemy.orm import selectinload

from app import db
from app.controllers.utils import atomic_transaction, Void
from app.data_access.activity import ActivityOutput
from app.domain.log_activities import log_activity
from app.domain.permissions import (
    check_actor_can_write_on_mission_over_period,
    check_actor_can_edit_activity,
    check_actor_can_log_without_mission_validation,
    company_admin,
)

from app.helpers.authentication import current_user, AuthenticatedMutation
from app.helpers.authorization import (
    with_authorization_policy,
    active,
)
from app.helpers.errors import (
    AuthorizationError,
    ResourceAlreadyDismissedError,
    InvalidParamsError,
)
from app.helpers.graphene_types import (
    graphene_enum_type,
    TimeStamp,
)
from app.models import User, Mission, MissionAutoValidation
from app.models.activity import Activity, ActivityType


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
    creation_time = graphene.Argument(
        TimeStamp,
        required=False,
        description="Optionnel, date de saisie de l'activité",
    )
    switch = graphene.Argument(
        graphene.Boolean,
        required=False,
        description="Optionnel, 'mode tachygraphe'. Dans ce mode l'enregistrement de la nouvelle activité met fin à l'activité en cours. Si l'option n'est pas activée et qu'il existe déjà une activité en cours l'enregistrement déclenchera une erreur. L'option ne peut être activée en même temps qu'une date de fin est spécifiée. Par défaut l'option est activée.",
    )


def log_activity_(input):
    switch_mode = input.get("switch", True)
    if switch_mode and input.get("end_time"):
        raise InvalidParamsError(
            "Specifying an end time is not authorized in switch mode"
        )

    reception_time = datetime.now()
    mission_id = input.get("mission_id")
    mission = Mission.query.options(selectinload(Mission.activities)).get(
        mission_id
    )
    user = current_user
    user_id = input.get("user_id")
    if user_id:
        user = User.query.get(user_id)

    is_user_admin = company_admin(current_user, mission.company_id)
    if not is_user_admin:
        existing_activities = [
            activity
            for activity in mission.activities
            if activity.user == user
        ]
        if len(existing_activities) == 0:
            auto_validation = MissionAutoValidation(
                mission=mission,
                is_admin=False,
                user=user,
                reception_time=reception_time,
            )
            db.session.add(auto_validation)

    activity = log_activity(
        submitter=current_user,
        user=user,
        mission=mission,
        type=input["type"],
        switch_mode=switch_mode,
        reception_time=reception_time,
        start_time=input["start_time"],
        end_time=input.get("end_time"),
        context=input.get("context"),
        creation_time=input.get("creation_time"),
    )

    ## Auto validation if user is not admin of the company and it's the first activity for this user for this mission

    return activity


class LogActivity(AuthenticatedMutation):
    """
    Enregistrement d'une nouvelle activité.

    Retourne l'activité nouvellement créée.
    """

    Arguments = ActivityLogInput

    Output = ActivityOutput

    @classmethod
    @with_authorization_policy(active)
    @with_authorization_policy(
        check_actor_can_log_without_mission_validation,
        get_target_from_args=lambda *args, **kwargs: {
            "mission": Mission.query.options(
                selectinload(Mission.activities)
            ).get(kwargs["mission_id"]),
            "user": User.query.get(kwargs["user_id"])
            if "user_id" in kwargs
            else None,
        },
        error_message="Actor is not authorized to log in the mission",
    )
    def mutate(cls, _, info, **activity_input):
        with atomic_transaction(commit_at_end=True):
            return log_activity_(input=activity_input)


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
    creation_time = graphene.Argument(
        TimeStamp,
        required=False,
        description="Optionnel, date de saisie de la modification de l'activité",
    )


def edit_activity_(input):
    if (
        not input.get("start_time")
        and not input.get("end_time")
        and not input.get("remove_end_time")
    ):
        raise InvalidParamsError(
            "At least one of startTime or endTime or removeEndTime should be set"
        )

    if input.get("end_time") and input.get("remove_end_time"):
        raise InvalidParamsError(
            "Either endTime or removeEndTime should be set but not both"
        )
    return edit_activity(
        input["activity_id"],
        cancel=False,
        start_time=input.get("start_time"),
        end_time=input.get("end_time"),
        remove_end_time=input.get("remove_end_time"),
        context=input.get("context"),
    )


def edit_activity(
    activity_id,
    cancel,
    start_time=None,
    end_time=None,
    remove_end_time=False,
    creation_time=None,
    context=None,
):
    reception_time = datetime.now()
    activity_to_update = Activity.query.get(activity_id)

    if not activity_to_update:
        raise AuthorizationError(
            f"Actor is not authorized to edit the activity"
        )

    mission = Mission.query.options(selectinload(Mission.activities)).get(
        activity_to_update.mission_id
    )

    check_actor_can_write_on_mission_over_period(
        current_user,
        mission,
        activity_to_update.user,
        activity_to_update.start_time,
        activity_to_update.end_time or activity_to_update.start_time,
    )

    if activity_to_update.is_dismissed:
        raise ResourceAlreadyDismissedError(f"Activity already dismissed.")

    db.session.add(activity_to_update)

    if cancel:
        activity_to_update.dismiss(reception_time, context)
    else:
        updates = {}
        if start_time:
            updates["start_time"] = start_time
        if end_time or remove_end_time:
            updates["end_time"] = end_time
        activity_to_update.revise(
            reception_time,
            revision_context=context,
            creation_time=creation_time,
            **updates,
        )

    return activity_to_update


class ActivityCancelInput:
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
    creation_time = graphene.Argument(
        TimeStamp,
        required=False,
        description="Optionnel, date de suppression de l'activité",
    )


class CancelActivity(AuthenticatedMutation):
    """
    Annulation d'une activité précédemment enregistrée.

    Retourne la liste des activités de la mission.
    """

    Arguments = ActivityCancelInput

    Output = Void

    @classmethod
    @with_authorization_policy(active)
    @with_authorization_policy(
        check_actor_can_edit_activity,
        get_target_from_args=lambda *args, **kwargs: Activity.query.get(
            kwargs["activity_id"]
        ),
        error_message="Actor is not authorized to edit the activity",
    )
    def mutate(cls, _, info, **edit_input):
        with atomic_transaction(commit_at_end=True):
            edit_activity(
                edit_input["activity_id"],
                cancel=True,
                context=edit_input.get("context"),
                creation_time=edit_input.get("creation_time"),
            )
        return Void(success=True)


class EditActivity(AuthenticatedMutation):
    """
    Correction d'une activité précédemment enregistrée.

    Retourne l'activité modifiée.
    """

    Arguments = ActivityEditInput

    Output = ActivityOutput

    @classmethod
    @with_authorization_policy(active)
    @with_authorization_policy(
        check_actor_can_edit_activity,
        get_target_from_args=lambda *args, **kwargs: Activity.query.get(
            kwargs["activity_id"]
        ),
        error_message="Actor is not authorized to edit the activity",
    )
    def mutate(cls, _, info, **edit_input):
        with atomic_transaction(commit_at_end=True):
            if (
                not edit_input.get("start_time")
                and not edit_input.get("end_time")
                and not edit_input.get("remove_end_time")
            ):
                raise InvalidParamsError(
                    "At least one of startTime or endTime or removeEndTime should be set"
                )

            if edit_input.get("end_time") and edit_input.get(
                "remove_end_time"
            ):
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
                creation_time=edit_input.get("creation_time"),
            )


def play_bulk_activity_items(items):
    res = None
    for item in items:
        if item.get("log"):
            input = item.get("log")
            res = log_activity_(input)
        if item.get("edit"):
            input = item.get("edit")
            res = edit_activity_(input)
        if item.get("cancel"):
            res = edit_activity(
                item.get("cancel")["activity_id"],
                cancel=True,
                context=item.get("cancel").get("context"),
            )
        db.session.flush()
    db.session().execute(
        "SET CONSTRAINTS no_overlapping_acknowledged_activities IMMEDIATE"
    )
    return res


class BulkActivityNewItem(graphene.InputObjectType, ActivityLogInput):
    pass


class BulkActivityEditItem(graphene.InputObjectType, ActivityEditInput):
    pass


class BulkActivityCancelItem(graphene.InputObjectType, ActivityCancelInput):
    pass


class BulkActivityItem(graphene.InputObjectType):
    log = graphene.Argument(BulkActivityNewItem, required=False)
    edit = graphene.Argument(BulkActivityEditItem, required=False)
    cancel = graphene.Argument(BulkActivityCancelItem, required=False)


class BulkActivity(graphene.ObjectType):
    """
    Valide une série de création/modification d'activités sans les sauvegarder en base.

    Retourne la dernière activité enregistrée ou modifiée.
    """

    output = graphene.Field(
        ActivityOutput,
        items=graphene.List(BulkActivityItem),
        description="Résultat de la dernière activité enregistrée ou modifiée",
    )

    @classmethod
    @with_authorization_policy(active)
    def resolve_output(cls, _, info, items=[]):
        with atomic_transaction(commit_at_end=False):
            return play_bulk_activity_items(items)
