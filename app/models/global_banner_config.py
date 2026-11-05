from enum import Enum

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.utils import enum_column


class GlobalBannerLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class GlobalBannerConfig(db.Model):
    __tablename__ = "global_banner_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    message = db.Column(db.Text, nullable=False)
    level = enum_column(GlobalBannerLevel, nullable=False)
    updated_at = db.Column(DateTimeStoredAsUTC, nullable=False)
    updated_by_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    updated_by = db.relationship("User")

    SINGLETON_ID = 1

    @classmethod
    def get_current(cls):
        return cls.query.get(cls.SINGLETON_ID)
