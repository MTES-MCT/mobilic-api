from enum import Enum
from datetime import datetime
from sqlalchemy.ext.declarative import declared_attr
from app.helpers.authentication import current_user
from sqlalchemy.orm import backref
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel
from app.models import User
from app import db
from app.models.utils import enum_column


class DismissType(str, Enum):
    USER_CANCEL = "user_cancel"


class EventBaseModel(BaseModel):
    __abstract__ = True

    backref_base_name = "events"

    reception_time = db.Column(db.DateTime, nullable=False)

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


class DeferrableEventBaseModel(EventBaseModel):
    __abstract__ = True

    start_time = db.Column(db.DateTime, nullable=False)

    @declared_attr
    def __table_args__(cls):
        return (
            db.CheckConstraint(
                f"(reception_time + interval '' >= start_time)",
                name=cls.__tablename__ + "_start_time_before_reception_time",
            ),
        )


class Dismissable:
    backref_base_name = "events"

    dismissed_at = db.Column(db.DateTime, nullable=True)
    dismiss_type = enum_column(DismissType, nullable=True)
    dismiss_received_at = db.Column(db.DateTime, nullable=True)

    dismiss_context = db.Column(JSONB(none_as_null=True), nullable=True)

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

    def dismiss(self, type, dismiss_time=None, context=None):
        self.dismiss_received_at = datetime.now()
        if not dismiss_time:
            dismiss_time = self.dismiss_received_at
        self.dismiss_context = context
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
    revision_context = db.Column(JSONB(none_as_null=True), nullable=True)

    @declared_attr
    def revised_by_id(cls):
        return db.Column(
            db.Integer,
            db.ForeignKey(cls.__tablename__ + ".id"),
            index=True,
            nullable=True,
        )

    @declared_attr
    def revised_by(cls):
        return db.relationship(
            cls,
            backref=backref("revisee", uselist=False),
            remote_side=[cls.id],
        )

    @property
    def is_revised(self):
        return self.revised_by is not None or self.revised_by_id is not None

    def set_revision(self, revision, context=None):
        self.revised_by = revision
        self.revision_context = context
