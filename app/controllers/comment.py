from flask_jwt_extended import current_user
from datetime import datetime
import graphene

from app import app
from app.controllers.event import (
    preload_or_create_relevant_resources_from_events,
)
from app.controllers.utils import atomic_transaction
from app.data_access.comment import CommentOutput
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
            preload_or_create_relevant_resources_from_events(
                events, User.comments
            )
            for group_comment in events:
                log_group_comment(
                    submitter=current_user,
                    users=[
                        User.query.get(uid) for uid in group_comment.user_ids
                    ],
                    content=group_comment.content,
                    event_time=group_comment.event_time,
                )

        return CommentLog(comments=current_user.comments,)
