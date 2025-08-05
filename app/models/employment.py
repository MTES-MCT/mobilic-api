from datetime import datetime
from enum import Enum

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.errors import AuthorizationError, InvalidResourceError
from app.helpers.validation import validate_email_field_in_db
from app.models.event import Dismissable, UserEventBaseModel
from app.models.mixins.has_business import HasBusiness
from app.models.team import Team
from app.models.utils import enum_column
from sqlalchemy import Index, text
from sqlalchemy.ext.declarative import declared_attr


class EmploymentRequestValidationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ContractType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"


class Employment(UserEventBaseModel, Dismissable, HasBusiness):
    backref_base_name = "employments"

    validation_time = db.Column(DateTimeStoredAsUTC, nullable=True)

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

    hide_email = db.Column(db.Boolean, nullable=False, default=False)

    team_id = db.Column(
        db.Integer, db.ForeignKey("team.id"), index=True, nullable=True
    )
    team = db.relationship(Team, backref="employments")

    # Needed for anonymization process if the submitter is still linked to an active user
    @declared_attr
    def submitter_id(cls):
        return db.Column(
            db.Integer,
            db.ForeignKey("user.id", onupdate="CASCADE"),
            index=True,
            nullable=False,
        )

    certificate_info_snooze_date = db.Column(db.Date, nullable=True)

    contract_type = enum_column(ContractType, nullable=True)
    part_time_percentage = db.Column(
        db.Integer,
        nullable=True,
    )
    contract_type_snooze_date = db.Column(db.Date, nullable=True)

    db.validates("email")(validate_email_field_in_db)

    __table_args__ = (
        db.Constraint(name="no_simultaneous_enrollments_for_the_same_company"),
        db.Constraint(name="no_undefined_employment_type_for_user"),
        db.CheckConstraint(
            "part_time_percentage IS NULL OR (part_time_percentage >= 10 AND part_time_percentage <= 90)",
            name="check_part_time_percentage_range",
        ),
        Index(
            "idx_employment_filters",
            "email",
            "user_id",
            "has_admin_rights",
            "validation_status",
            "creation_time",
            postgresql_where=text(
                "user_id IS NULL AND has_admin_rights = false"
            ),
        ),
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
    def should_see_certificate_info(self):
        if not self.has_admin_rights:
            return False
        if self.certificate_info_snooze_date is None:
            return True
        return self.certificate_info_snooze_date < datetime.now().date()

    @property
    def should_specify_contract_type(self):
        if not self.has_admin_rights:
            return False
        if self.contract_type is not None:
            return False

        if self.contract_type_snooze_date is None:
            return True

        from datetime import timedelta

        deadline = self.contract_type_snooze_date + timedelta(days=15)
        return datetime.now().date() >= deadline

    @property
    def contract_type_deadline_passed(self):
        if self.contract_type is not None:
            return False

        if self.contract_type_snooze_date is None:
            return False

        from datetime import timedelta

        deadline = self.contract_type_snooze_date + timedelta(days=15)
        return datetime.now().date() > deadline

    @property
    def is_acknowledged(self):
        return (
            self.validation_status
            == EmploymentRequestValidationStatus.APPROVED
            and not self.is_dismissed
        )

    def bind(self, user):
        self.user_id = user.id
        for email in self.invite_emails:
            email.user_id = user.id

    def validate_by(self, user, time=None, reject=False):
        if self.user_id != user.id:
            raise AuthorizationError(
                "Actor is not authorized to review the employment"
            )

        if (
            self.validation_status != EmploymentRequestValidationStatus.PENDING
            or self.is_dismissed
        ):
            raise InvalidResourceError(
                f"Employment is already {'validated' if self.is_acknowledged else 'dismissed' if self.is_dismissed else 'rejected'}"
            )

        self.validation_status = (
            EmploymentRequestValidationStatus.APPROVED
            if not reject
            else EmploymentRequestValidationStatus.REJECTED
        )
        self.validation_time = time if time else datetime.now()

        _bind_users_to_team(
            user_ids=[user.id],
            team_id=self.team_id,
            company_id=self.company_id,
        )

    @property
    def latest_invite_email_time(self):
        invite_emails = self.invite_emails
        if not invite_emails:
            return None
        return max([e.creation_time for e in invite_emails])


def _bind_users_to_team(user_ids, team_id, company_id):
    Employment.query.filter(
        Employment.company_id == company_id,
        Employment.user_id.in_(user_ids),
    ).update({"team_id": team_id}, synchronize_session=False)


def _bind_employment_to_team(employment_id, team_id):
    Employment.query.filter(
        Employment.id == employment_id,
    ).update({"team_id": team_id}, synchronize_session=False)
