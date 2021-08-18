from app import db
from app.helpers.graphene_types import BaseSQLAlchemyObjectType
from app.helpers.mail_type import EmailType
from app.models.base import BaseModel
from app.models.utils import enum_column


class Email(BaseModel):
    mailjet_id = db.Column(db.TEXT, unique=True, nullable=False)

    address = db.Column(db.TEXT, nullable=False)

    type = enum_column(EmailType, nullable=False)

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True, index=True
    )
    user = db.relationship("User", backref="emails")

    employment_id = db.Column(
        db.Integer, db.ForeignKey("employment.id"), nullable=True, index=True
    )
    employment = db.relationship("Employment", backref="invite_emails")


class EmailOutput(BaseSQLAlchemyObjectType):
    class Meta:
        model = Email
        only_fields = (
            "id",
            "creation_time",
            "type",
            "address",
        )
