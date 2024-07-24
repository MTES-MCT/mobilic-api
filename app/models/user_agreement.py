from sqlalchemy.orm import backref
from app import db
from app.models.base import BaseModel


class UserAgreement(BaseModel):
    backref_base_name = "user_agreements"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    user = db.relationship(
        "User", backref=backref("user_agreements", lazy=True)
    )
    cgu_version = db.Column(db.String(5), nullable=False, index=True)
    answer_date = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )
    status = db.Column(db.String(10), nullable=False)
    expires_at = db.Column(db.DateTime)
    has_transferred_data = db.Column(db.DateTime)
    is_blacklisted = db.Column(db.Boolean)

    __table_args__ = (
        db.CheckConstraint(
            status.in_(["pending", "accepted", "rejected"]),
            name="check_status_valid",
        ),
    )
