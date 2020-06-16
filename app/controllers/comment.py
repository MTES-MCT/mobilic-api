from app.helpers.authentication import current_user
import graphene

from app import app
from app.controllers.utils import atomic_transaction
from app.models import Mission
from app.models.comment import CommentOutput
from app.domain.log_comments import log_comment
from app.helpers.authorization import with_authorization_policy, authenticated
from app.controllers.event import EventInput


class LogComment(graphene.Mutation):
    """
    Ajout d'un commentaire sur la mission.

    Retourne le commentaire nouvellement ajouté.
    """

    class Arguments(EventInput):
        content = graphene.String(
            required=True, description="Texte du commentaire"
        )
        mission_id = graphene.Int(
            required=True, description="Identifiant de la mission"
        )

    Output = CommentOutput

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, **comment_input):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(f"Logging comment")
            mission_id = comment_input.get("mission_id")
            mission = Mission.query.get(mission_id)

            comment = log_comment(
                submitter=current_user,
                mission=mission,
                content=comment_input["content"],
                event_time=comment_input["event_time"],
            )

        return comment
