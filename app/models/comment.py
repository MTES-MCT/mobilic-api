import graphene
from sqlalchemy.orm import backref

from app import db
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
)
from app.models.event import EventBaseModel, Dismissable


class Comment(EventBaseModel, Dismissable):
    backref_base_name = "comments"

    mission_id = db.Column(
        db.Integer, db.ForeignKey("mission.id"), index=True, nullable=False
    )
    mission = db.relationship("Mission", backref=backref("comments"))
    text = db.Column(db.TEXT, nullable=False)


class CommentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Comment
        only_fields = (
            "id",
            "reception_time",
            "mission_id",
            "mission",
            "text",
            "submitter_id",
            "submitter",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant du commentaire"
    )
    mission_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la mission à laquelle se rattache le commentaire",
    )
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )
    submitter_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de la personne qui a écrit le commentaire",
    )
    text = graphene.String(required=True, description="Contenu du commentaire")
