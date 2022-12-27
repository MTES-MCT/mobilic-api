from enum import Enum
from datetime import datetime
import graphene

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.helpers.errors import AuthorizationError, InvalidResourceError
from app.helpers.graphene_types import (
    BaseSQLAlchemyObjectType,
    TimeStamp,
)
from app.helpers.validation import validate_email_field_in_db
from app.models.event import UserEventBaseModel, Dismissable
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
    external_id = db.Column(db.String(255), nullable=True)

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

    @property
    def latest_invite_email_time(self):
        invite_emails = self.invite_emails
        if not invite_emails:
            return None
        return max([e.creation_time for e in invite_emails])


class EmploymentOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Employment
        only_fields = (
            "id",
            "reception_time",
            "start_date",
            "end_date",
            "user_id",
            "user",
            "submitter_id",
            "submitter",
            "company_id",
            "company",
            "has_admin_rights",
            "email",
            "latest_invite_email_time",
            "external_id",
        )

    id = graphene.Field(
        graphene.Int, required=True, description="Identifiant du rattachement"
    )
    reception_time = graphene.Field(
        TimeStamp,
        required=True,
        description="Horodatage de création de l'entité",
    )
    user_id = graphene.Field(
        graphene.Int,
        description="Identifiant de l'utilisateur concerné par le rattachement. Peut être manquant dans le cas d'une invitation par email",
    )
    submitter_id = graphene.Field(
        graphene.Int,
        description="Identifiant de la personne qui a créé le rattachement",
    )
    start_date = graphene.Field(
        graphene.String,
        required=True,
        description="Date de début du rattachement au format AAAA-MM-JJ",
    )
    end_date = graphene.Field(
        graphene.String,
        description="Date de fin du rattachement au format AAAA-MM-JJ, si présente.",
    )
    company_id = graphene.Field(
        graphene.Int,
        required=True,
        description="Identifiant de l'entreprise de rattachement",
    )
    has_admin_rights = graphene.Field(
        graphene.Boolean,
        description="Précise si le rattachement confère un accès gestionnaire ou non. Une valeur manquante équivaut à non.",
    )
    email = graphene.Field(
        graphene.String,
        description="Email éventuel vers lequel est envoyée l'invitation.",
    )

    is_acknowledged = graphene.Field(
        graphene.Boolean,
        description="Précise si le rattachement a été approuvé par l'utilisateur concerné ou s'il est en attente de validation. Un rattachement non validé ne peut pas être actif.",
    )
    latest_invite_email_time = graphene.Field(
        TimeStamp,
        required=False,
        description="Horodatage d'envoi du dernier email d'invitation",
    )
    external_id = graphene.Field(
        graphene.String,
        description="Identifiant du salarié dans le logiciel tiers",
    )

    def resolve_is_acknowledged(self, info):
        return self.is_acknowledged
