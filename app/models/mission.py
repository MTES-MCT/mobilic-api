from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.event import DeferrableEventBaseModel


class Mission(DeferrableEventBaseModel):
    backref_base_name = "missions"

    name = db.Column(db.TEXT, nullable=False)


class MissionOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Mission
