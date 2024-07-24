from enum import Enum

from sqlalchemy.orm import backref
from app import db
from app.models.base import BaseModel
from app.models.utils import enum_column


class UserAgreementStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    __description__ = """
    - "pending" : l'utilisateur n'a pas encore accepté ou refusé les cgus.
    - "accepted" : l'utilisateur a accepté les cgus
    - "rejected" : l'utilisateur a refusé les cgus
    """


CGU_INITIAL_VERSION = "v1.0"


class UserAgreement(BaseModel):
    backref_base_name = "user_agreements"

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship(
        "User", backref=backref("user_agreements", lazy=True)
    )
    cgu_version = db.Column(db.String(5), nullable=False, index=True)
    answer_date = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )
    status = enum_column(UserAgreementStatus, nullable=False)
    expires_at = db.Column(db.DateTime)
    has_transferred_data = db.Column(db.DateTime)
    is_blacklisted = db.Column(db.Boolean)

    __table_args__ = (
        db.UniqueConstraint("user_id", "cgu_version", name="unique_user_cgu"),
    )
