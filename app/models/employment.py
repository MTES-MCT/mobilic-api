from datetime import datetime
from enum import Enum

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.errors import AuthorizationError, InvalidResourceError
from app.helpers.validation import validate_email_field_in_db
from app.models.event import Dismissable, UserEventBaseModel
from app.models.team import Team
from app.models.utils import enum_column


class EmploymentRequestValidationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Employment(UserEventBaseModel, Dismissable):
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

    team_id = db.Column(
        db.Integer, db.ForeignKey("team.id"), index=True, nullable=True
    )
    team = db.relationship(Team, backref="employments")

    db.validates("email")(validate_email_field_in_db)

    __table_args__ = (
        db.Constraint(name="no_simultaneous_enrollments_for_the_same_company"),
        db.Constraint(name="no_undefined_employment_type_for_user"),
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
            and not self.is_dismissed
        )

    def bind(self, user):
        self.user_id = user.id
        for email in self.invite_emails:
            email.user_id = user.id

    def validate_by(self, user, time=None, reject=False):
        if not self.user_id == user.id:
            raise AuthorizationError(
                "Actor is not authorized to review the employment"
            )

        if (
            not self.validation_status
            == EmploymentRequestValidationStatus.PENDING
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
