import graphene

from app import db
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import UserEventBaseModel, Dismissable, DismissType


class Comment(UserEventBaseModel, Dismissable):
    backref_base_name = "comments"

    content = db.Column(db.TEXT, nullable=False)


class CommentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Comment

    team = graphene.List(graphene.Int)
    dismiss_type = graphene_enum_type(DismissType)(required=False)
