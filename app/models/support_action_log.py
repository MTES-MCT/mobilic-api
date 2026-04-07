from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel


class SupportActionLog(BaseModel):
    __tablename__ = "support_action_log"

    support_user_id = db.Column(
        db.Integer,
        nullable=False,
        index=True,
    )
    impersonated_user_id = db.Column(
        db.Integer,
        nullable=False,
        index=True,
    )
    table_name = db.Column(db.String(255), nullable=False)
    row_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(10), nullable=False)
    old_values = db.Column(JSONB(none_as_null=True), nullable=True)
    new_values = db.Column(JSONB(none_as_null=True), nullable=True)
