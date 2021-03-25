from enum import Enum
from datetime import datetime
from sqlalchemy.ext.declarative import declared_attr
from app.helpers.authentication import current_user
from sqlalchemy.orm import backref
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import JSONB

from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel
from app.models import User
from app import db
from app.models.utils import enum_column


class EventBaseModel(BaseModel):
    __abstract__ = True

    backref_base_name = "events"

    reception_time = db.Column(DateTimeStoredAsUTC, nullable=False)

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

    start_time = db.Column(DateTimeStoredAsUTC, nullable=False)

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

    dismissed_at = db.Column(DateTimeStoredAsUTC, nullable=True)

    dismiss_context = db.Column(JSONB(none_as_null=True), nullable=True)

    @hybrid_property
    def is_dismissed(self):
        return self.dismissed_at is not None

    @is_dismissed.expression
    def is_dismissed(cls):
        return cls.dismissed_at.isnot(None)

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

    def dismiss(self, dismiss_time=None, context=None):
        if not dismiss_time:
            dismiss_time = datetime.now()
        self.dismiss_context = context
        self.dismissed_at = dismiss_time
        self.dismiss_author = current_user

    __table_args__ = (
        db.CheckConstraint(
            "((dismissed_at is not null)::bool = (dismiss_author_id is not null)::bool)",
            "non_nullable_dismiss_info",
        ),
    )


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
