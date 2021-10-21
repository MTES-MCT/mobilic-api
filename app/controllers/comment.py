from sqlalchemy.orm import selectinload

from app.domain.permissions import can_actor_read_mission
from app.helpers.authentication import current_user, AuthenticatedMutation
import graphene
from datetime import datetime

from app import db
from app.controllers.utils import atomic_transaction, Void
from app.helpers.errors import AuthorizationError, InvalidParamsError
from app.helpers.authorization import (
    with_authorization_policy,
    active,
)
from app.models import Comment, Mission
from app.models.comment import CommentOutput


class CommentInput:
    text = graphene.Argument(
        graphene.String,
        required=True,
        description="Contenu de l'observation",
    )
    mission_id = graphene.Int(
        required=True,
        description="Identifiant de la mission à laquelle se rattache l'observation",
    )


class LogComment(AuthenticatedMutation):
    """
    Ajout d'une observation à la mission.

    Retourne l'observation nouvellement créée.
    """

    Arguments = CommentInput

    Output = CommentOutput

    @classmethod
    @with_authorization_policy(
        can_actor_read_mission,
        get_target_from_args=lambda *args, **kwargs: Mission.query.options(
            selectinload(Mission.activities)
        ).get(kwargs["mission_id"]),
        error_message="Actor is not authorized to comment on this mission.",
    )
    def mutate(cls, _, info, **comment_input):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            mission_id = comment_input.get("mission_id")
            mission = Mission.query.get(mission_id)

            if not comment_input["text"]:
                raise InvalidParamsError("Cannot create an empty comment.")

            comment = Comment(
                submitter=current_user,
                mission=mission,
                text=comment_input["text"],
                reception_time=reception_time,
            )
            db.session.add(comment)

        return comment


class CancelComment(AuthenticatedMutation):
    """
    Retrait d'une observation.

    Retourne un message de succès.
    """

    class Arguments:
        comment_id = graphene.Argument(
            graphene.Int,
            required=True,
            description="Identifiant de l'observation à retirer.",
        )

    Output = Void

    @classmethod
    @with_authorization_policy(active)
    def mutate(cls, _, info, comment_id):
        with atomic_transaction(commit_at_end=True):
            reception_time = datetime.now()
            comment_to_dismiss = Comment.query.get(comment_id)

            if (
                not comment_to_dismiss
                or current_user.id != comment_to_dismiss.submitter_id
            ):
                raise AuthorizationError(
                    "Actor is not authorized to dismiss the comment."
                )

            db.session.add(comment_to_dismiss)
            comment_to_dismiss.dismiss(reception_time)

        return Void(success=True)
