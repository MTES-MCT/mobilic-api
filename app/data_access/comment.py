import graphene

from app.models import Comment
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import EventBaseContext


class CommentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Comment

    team = graphene.List(graphene.Int)
    context = graphene_enum_type(EventBaseContext)()
