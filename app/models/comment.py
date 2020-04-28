from sqlalchemy.orm import backref

from app import db
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import EventBaseModel, Dismissable, DismissType


class Comment(EventBaseModel, Dismissable):
    backref_base_name = "comments"

    content = db.Column(db.TEXT, nullable=False)

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("comments"))


class CommentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Comment

    dismiss_type = graphene_enum_type(DismissType)(required=False)
