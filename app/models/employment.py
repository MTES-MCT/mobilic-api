from enum import Enum
from datetime import datetime
import graphene

from app import db
from app.helpers.errors import (
    EmploymentAlreadyReviewedByUserError,
    AuthorizationError,
)
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    graphene_enum_type,
)
from app.models.event import UserEventBaseModel
from app.models.utils import enum_column


class EmploymentRequestValidationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Employment(UserEventBaseModel):
    backref_base_name = "employments"

    is_primary = db.Column(db.Boolean, nullable=False, default=True)

    validation_time = db.Column(db.DateTime, nullable=True)

    validation_status = enum_column(
        EmploymentRequestValidationStatus, nullable=False
    )

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)

    company_id = db.Column(
        db.Integer, db.ForeignKey("company.id"), index=True, nullable=False
    )
    company = db.relationship("Company", backref="employments")

    has_admin_rights = db.Column(db.Boolean, nullable=True)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), index=True, nullable=True
    )
    email = db.Column(db.String(255), nullable=True)
    invite_token = db.Column(db.String(255), nullable=True, unique=True)

    __table_args__ = (
        db.Constraint(name="only_one_current_primary_enrollment_per_user"),
        db.Constraint(name="no_simultaneous_enrollments_for_the_same_company"),
    )

    def __repr__(self):
        return f"<Employment [{self.id}] of User {self.user_id} in Company {self.company_id}>"

    @property
    def is_not_rejected(self):
        return (
            self.validation_status
            != EmploymentRequestValidationStatus.REJECTED
        )

    @property
    def is_acknowledged(self):
        return (
            self.validation_status
            == EmploymentRequestValidationStatus.APPROVED
        )

    def validate_by(self, user, time=None, reject=False):
        if (
            not self.validation_status
            == EmploymentRequestValidationStatus.PENDING
        ):
            raise EmploymentAlreadyReviewedByUserError(
                f"Employment is already {'validated' if self.is_acknowledged else 'rejected'}"
            )

        if not self.user_id == user.id:
            raise AuthorizationError(
                f"The user is not authorized to review the employment"
            )

        self.validation_status = (
            EmploymentRequestValidationStatus.APPROVED
            if not reject
            else EmploymentRequestValidationStatus.REJECTED
        )
        self.validation_time = time if time else datetime.now()


class EmploymentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Employment

    validation_status = graphene_enum_type(EmploymentRequestValidationStatus)()
    is_acknowledged = graphene.Field(graphene.Boolean)

    def resolve_is_acknowledged(self, info):
        return self.is_acknowledged
