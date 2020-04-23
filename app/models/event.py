from enum import Enum
from datetime import datetime
from sqlalchemy.ext.declarative import declared_attr
from flask_jwt_extended import current_user
from sqlalchemy.orm import backref

from app.models.base import BaseModel
from app.models import User
from app import db
from app.models.utils import enum_column


class DismissType(str, Enum):
    UNAUTHORIZED_SUBMITTER = "unauthorized_submitter"
    USER_CANCEL = "user_cancel"


class EventBaseModel(BaseModel):
    __abstract__ = True

    backref_base_name = "events"

    event_time = db.Column(db.DateTime, nullable=False)

    @declared_attr
    def submitter_id(cls):
        return db.Column(
            db.Integer, db.ForeignKey("user.id"), index=True, nullable=False
        )

    @declared_attr
    def submitter(cls):
        return db.relationship(
            User,
            # primaryjoin=lambda: User.id == cls.submitter_id,
            foreign_keys=[cls.submitter_id],
            backref="submitted_" + cls.backref_base_name,
        )

    @property
    def authorized_submit(self):
        return self.dismiss_type != DismissType.UNAUTHORIZED_SUBMITTER

    def to_dict(self):
        return dict(
            id=self.id,
            event_time=self.event_time,
            user=self.user.to_dict(),
            company=self.company.to_dict(),
            submitter=self.submitter.to_dict(),
        )


class DeferrableEventBaseModel(EventBaseModel):
    __abstract__ = True

    user_time = db.Column(db.DateTime, nullable=False)

    @declared_attr
    def __table_args__(cls):
        return (
            db.CheckConstraint(
                "(event_time >= user_time)",
                name=cls.__tablename__ + "_user_time_before_event_time",
            ),
        )


class Dismissable:
    dismissed_at = db.Column(db.DateTime, nullable=True)
    dismiss_type = enum_column(DismissType, nullable=True)
    dismiss_received_at = db.Column(db.DateTime, nullable=True)

    dismiss_comment = db.Column(db.TEXT, nullable=True)

    @property
    def is_dismissed(self):
        return self.dismissed_at is not None

    @declared_attr
    def dismiss_author_id(cls):
        return db.Column(
            db.Integer, db.ForeignKey("user.id"), index=True, nullable=True
        )

    @declared_attr
    def dismiss_author(cls):
        return db.relationship(
            User,
            foreign_keys=[cls.dismiss_author_id],
            backref="dismissed_" + cls.backref_base_name,
        )

    def dismiss(self, type, dismiss_time=None, comment=None):
        self.dismiss_received_at = datetime.now()
        if not dismiss_time:
            dismiss_time = self.dismiss_received_at
        self.dismiss_comment = comment
        self.dismiss_type = type
        self.dismissed_at = dismiss_time
        self.dismiss_author = current_user

    __table_args__ = (
        db.CheckConstraint(
            "((dismissed_at is not null)::bool = (dismiss_type is not null)::bool AND (dismiss_type is not null)::bool = (dismiss_received_at is not null)::bool)",
            "non_nullable_dismiss_type",
        ),
        db.CheckConstraint(
            "(dismiss_type != 'user_cancel' OR dismiss_author_id is not null)",
            "non_nullable_dismiss_author_id",
        ),
    )

    @property
    def is_acknowledged(self):
        return not self.is_dismissed


class UserEventBaseModel(EventBaseModel):
    __abstract__ = True

    @declared_attr
    def user_id(cls):
        return db.Column(
            db.Integer, db.ForeignKey("user.id"), index=True, nullable=False
        )

    @declared_attr
    def user(cls):
        return db.relationship(
            User,
            # primaryjoin=lambda: User.id == cls.user_id,
            foreign_keys=[cls.user_id],
            backref=cls.backref_base_name,
        )


class Revisable(Dismissable):
    revision_comment = db.Column(db.TEXT, nullable=True)

    @declared_attr
    def revisee_id(cls):
        return db.Column(
            db.Integer,
            db.ForeignKey(cls.__tablename__ + ".id"),
            index=True,
            nullable=True,
        )

    @declared_attr
    def revisee(cls):
        return db.relationship(
            cls,
            backref=backref("revised_by", lazy="selectin"),
            remote_side=[cls.id],
        )

    @property
    def is_revised(self):
        return len([e for e in self.revised_by if e.authorized_submit]) > 0

    def set_revision(self, revision, comment=None):
        revision.revisee = self
        revision.revision_comment = comment
