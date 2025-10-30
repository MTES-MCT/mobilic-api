from enum import Enum

from app import db
from app.models.base import BaseModel
from app.models.utils import enum_column


class ExportType(str, Enum):
    EXCEL = "excel"


class ExportStatus(str, Enum):
    WIP = "work_in_progress"
    READY = "ready"
    DOWNLOADED = "downloaded"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Export(BaseModel):
    backref_base_name = "exports"

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    user = db.relationship("User", backref="exports")
    file_name = db.Column(db.String, nullable=True)
    file_type = db.Column(db.String, nullable=True)

    export_type = enum_column(
        ExportType,
        nullable=False,
        default=ExportType.EXCEL,
        server_default=ExportType.EXCEL.value,
    )
    status = enum_column(
        ExportStatus,
        nullable=False,
        default=ExportStatus.WIP,
        server_default=ExportStatus.WIP.value,
    )
