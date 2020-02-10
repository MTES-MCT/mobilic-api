from enum import Enum
from sqlalchemy.ext.declarative import declared_attr

from app.models.base import BaseModel
from app.models import User, Company
from app import db
from app.models.utils import enum_column


class EventBaseValidationStatus(str, Enum):
    VALIDATED = "validated"
    PENDING = "pending"
    REJECTED = "rejected"
    UNAUTHORIZED_SUBMITTER = ("unauthorized_submitter",)


class EventBaseModel(BaseModel):
    __abstract__ = True

    backref_base_name = "events"

    event_time = db.Column(db.DateTime, nullable=False)
    reception_time = db.Column(db.DateTime, nullable=False)

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

    @declared_attr
    def company_id(cls):
        return db.Column(
            db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
        )

    @declared_attr
    def company(cls):
        return db.relationship(
            Company,
            # primaryjoin=lambda: Company.id == cls.user_id,
            foreign_keys=[cls.company_id],
            backref=cls.backref_base_name,
        )

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

    validation_status = enum_column(EventBaseValidationStatus, nullable=False)

    @property
    def is_acknowledged(self):
        return self.validation_status in [
            EventBaseValidationStatus.PENDING,
            EventBaseValidationStatus.VALIDATED,
        ]

    def to_dict(self):
        return dict(
            id=self.id,
            event_time=self.event_time,
            user=self.user.to_dict(),
            company=self.company.to_dict(),
            submitter=self.submitter.to_dict(),
            validation_status=self.validation_status,
        )
