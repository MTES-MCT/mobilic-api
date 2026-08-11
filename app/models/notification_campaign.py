from enum import Enum

from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel
from app.models.utils import enum_column


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CampaignTargetType(str, Enum):
    ALL_USERS = "all_users"
    ALL_EMPLOYEES = "all_employees"
    ALL_MANAGERS = "all_managers"
    SPECIFIC_EMPLOYEES = "specific_employees"
    SPECIFIC_MANAGERS = "specific_managers"


class NotificationCampaign(BaseModel):
    __tablename__ = "notification_campaign"

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    created_by = db.relationship("User")

    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)

    target_type = enum_column(CampaignTargetType, nullable=False)
    target_user_ids = db.Column(
        JSONB(none_as_null=True), nullable=True
    )

    scheduled_at = db.Column(DateTimeStoredAsUTC, nullable=True)
    celery_task_id = db.Column(db.String(255), nullable=True)

    status = enum_column(
        CampaignStatus,
        nullable=False,
        default=CampaignStatus.DRAFT,
        server_default=CampaignStatus.DRAFT.value,
    )

    targeted_count = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )
    total_recipients = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )
    sent_count = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )
    failed_count = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )
    clicked_count = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )

    completed_at = db.Column(DateTimeStoredAsUTC, nullable=True)
