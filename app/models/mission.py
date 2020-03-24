from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.models.event import EventBaseModel


class Mission(EventBaseModel):
    backref_base_name = "missions"

    name = db.Column(db.TEXT, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            "(event_time >= start_time)",
            name="mission_start_time_before_event_time",
        ),
    )


class MissionOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Mission
