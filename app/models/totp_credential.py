from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel


class TotpCredential(BaseModel):
    __tablename__ = "totp_credential"

    owner_type = db.Column(db.String(50), nullable=False)
    owner_id = db.Column(db.Integer, nullable=False)
    secret = db.Column(db.String(255), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    last_failed_at = db.Column(DateTimeStoredAsUTC, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "owner_type",
            "owner_id",
            name="uq_totp_credential_owner",
        ),
    )
