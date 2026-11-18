from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.models.base import BaseModel


class PlatformHealthCheckRun(BaseModel):
    __tablename__ = "platform_health_check_run"

    # [label, error] pairs of the failed checks; empty when every check passed.
    failures = db.Column(JSONB, nullable=False, default=list)
