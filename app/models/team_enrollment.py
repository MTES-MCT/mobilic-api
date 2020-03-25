from enum import Enum
from flask_jwt_extended import current_user

from app import db
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import UserEventBaseModel, Revisable, DismissType
from app.models.utils import enum_column


class TeamEnrollmentType(str, Enum):
    ENROLL = "enroll"
    REMOVE = "remove"


class TeamEnrollment(UserEventBaseModel, Revisable):
    backref_base_name = "team_enrollments"

    type = enum_column(TeamEnrollmentType, nullable=False)
    action_time = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            "(event_time >= action_time)",
            name="team_enrollment_action_time_before_event_time",
        ),
        db.CheckConstraint(
            "(submitter_id != user_id)",
            name="team_enrollment_cannot_target_self",
        ),
    )

    def revise(self, revision_time, **updated_props):
        if self.is_dismissed:
            raise ValueError(f"You can't revise the already dismissed {self}")
        if not self.id:
            for prop, value in updated_props.items():
                setattr(self, prop, value)
            db.session.add(self)
            return self
        dict_ = dict(
            type=self.type,
            event_time=revision_time,
            action_time=self.action_time,
            user=self.user,
            company_id=self.company_id,
            submitter=current_user,
        )
        dict_.update(updated_props)
        revision = TeamEnrollment(**dict_)
        self.set_revision(revision)
        db.session.add(revision)
        return revision


class TeamEnrollmentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = TeamEnrollment

    type = graphene_enum_type(TeamEnrollmentType)()
    dismiss_type = graphene_enum_type(DismissType)(required=False)
