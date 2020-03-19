from enum import Enum

from app import db
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import EventBaseModel, DismissType
from app.models.utils import enum_column


class TeamEnrollmentType(str, Enum):
    ENROLL = "enroll"
    REMOVE = "remove"


class TeamEnrollment(EventBaseModel):
    backref_base_name = "team_enrollments"

    type = enum_column(TeamEnrollmentType, nullable=False)
    action_time = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        base_dict = super().to_dict()
        return dict(**base_dict, type=self.type,)


class TeamEnrollmentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = TeamEnrollment

    type = graphene_enum_type(TeamEnrollmentType)()
    dismiss_type = graphene_enum_type(DismissType)(required=False)
