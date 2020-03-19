from flask_jwt_extended import current_user
import graphene

from app import app
from app.controllers.event import preload_relevant_resources_for_event_logging
from app.controllers.utils import atomic_transaction
from app.models.comment import CommentOutput
from app.domain.log_comments import log_group_comment
from app.helpers.authorization import with_authorization_policy, authenticated
from app.models.user import User
from app.controllers.event import EventInput


class CommentInput(EventInput):
    content = graphene.Field(graphene.String)


class CommentLog(graphene.Mutation):
    class Arguments:
        data = graphene.List(CommentInput, required=True)

    comments = graphene.List(CommentOutput)

    @classmethod
    @with_authorization_policy(authenticated)
    def mutate(cls, _, info, data):
        with atomic_transaction(commit_at_end=True):
            app.logger.info(
                f"Logging comments submitted by {current_user} of company {current_user.company}"
            )
            events = sorted(data, key=lambda e: e.event_time)
            preload_relevant_resources_for_event_logging(User.comments)
            for group_comment in events:
                log_group_comment(
                    submitter=current_user,
                    users=[current_user]
                    + current_user.acknowledged_team_at(
                        group_comment.event_time
                    ),
                    content=group_comment.content,
                    event_time=group_comment.event_time,
                )

        return CommentLog(comments=current_user.comments,)
