from enum import Enum
from flask_jwt_extended import current_user

from app import app, db
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import (
    DismissType,
    UserEventBaseModel,
    DeferrableEventBaseModel,
    Revisable,
)
from app.models.utils import enum_column


class InputableActivityType(str, Enum):
    DRIVE = "drive"
    WORK = "work"
    BREAK = "break"
    REST = "rest"


ActivityType = Enum(
    "ActivityTypes",
    dict(
        SUPPORT="support",
        **{
            activity.name: activity.value for activity in InputableActivityType
        },
    ),
    type=str,
)


ActivityDismissType = Enum(
    "ActivityDismissType",
    dict(
        NO_ACTIVITY_SWITCH="no_activity_switch",
        **{
            dismiss_type.name: dismiss_type.value
            for dismiss_type in DismissType
        },
    ),
)


class Activity(UserEventBaseModel, DeferrableEventBaseModel, Revisable):
    backref_base_name = "activities"

    type = enum_column(ActivityType, nullable=False)

    vehicle_registration_number = db.Column(db.String(255))
    mission = db.Column(db.String(255))

    driver_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=False)
    driver = db.relationship("User", foreign_keys=[driver_id])

    team = db.Column(db.ARRAY(db.Integer), nullable=True)

    is_driver_switch = db.Column(db.Boolean, nullable=True, default=None)

    dismiss_type = enum_column(ActivityDismissType, nullable=True)

    creation_comment = db.Column(db.TEXT, nullable=True)

    # TODO : add (maybe)
    # - validator
    # - version (each version represents a set of changes to the day activities)
    # OR revises (indicates which prior activity the current one revises)

    def __repr__(self):
        return f"<Activity [{self.id}] : {self.type.value}>"

    @property
    def is_acknowledged(self):
        return not self.is_dismissed and not self.is_revised

    @property
    def previous_and_next_acknowledged_activities(self):
        previous_activity = None
        for activity in self.user.acknowledged_activities:
            if activity.user_time > self.user_time:
                return previous_activity, activity
            if activity != self:
                previous_activity = activity
        return previous_activity, None

    @property
    def previous_acknowledged_activity(self):
        return self.previous_and_next_acknowledged_activities[0]

    @property
    def next_acknowledged_activity(self):
        return self.previous_and_next_acknowledged_activities[1]

    @property
    def is_duplicate(self):
        return (
            self.is_driver_switch
            or self.dismiss_type == ActivityDismissType.NO_ACTIVITY_SWITCH
        )

    def revise(self, revision_time, revision_comment=None, **updated_props):
        from app.domain.log_activities import log_activity

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
            user_time=self.user_time,
            user=self.user,
            submitter=current_user,
            vehicle_registration_number=self.vehicle_registration_number,
            driver=self.driver,
        )
        dict_.update(updated_props)
        revision = log_activity(**dict_)
        if not revision:
            app.logger.warning(
                f"Could not create revision for {self} with arguments {updated_props}"
            )
            return None
        self.set_revision(revision, revision_comment)
        db.session.add(revision)
        return revision


class ActivityOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Activity

    type = graphene_enum_type(ActivityType)()
    dismiss_type = graphene_enum_type(ActivityDismissType)(required=False)
