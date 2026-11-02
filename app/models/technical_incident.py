from datetime import datetime, timedelta
from enum import Enum

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel
from app.models.utils import enum_column

# Past this window, an incident left open is shown as ended (end capped) without
# ever persisting a fabricated end_time.
ONGOING_INCIDENT_MAX_VISIBLE_DURATION = timedelta(hours=48)


class TechnicalIncidentType(str, Enum):
    # Infrastructure
    SERVER_DOWN = "server_down"
    DNS_SWITCH = "dns_switch"
    SSL_EXPIRED = "ssl_expired"
    DATABASE_DOWN = "database_down"
    BACKEND_API_UNAVAILABLE = "backend_api_unavailable"
    # Application
    SLOWDOWN_TIMEOUT = "slowdown_timeout"
    DEPLOY_REGRESSION = "deploy_regression"
    TIME_ENTRY_BUG = "time_entry_bug"
    OFFLINE_SYNC_BUG = "offline_sync_bug"
    # Access / external dependencies
    AUTH_OUTAGE = "auth_outage"
    EMAIL_UNAVAILABLE = "email_unavailable"
    THIRD_PARTY_OUTAGE = "third_party_outage"
    # Special case
    PLANNED_MAINTENANCE = "planned_maintenance"


class TechnicalIncidentCategory(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    APPLICATIVE = "applicative"
    ACCESS_EXTERNAL = "access_external"
    SPECIAL_CASE = "special_case"


class TechnicalIncidentNature(str, Enum):
    PLATFORM_UNAVAILABLE = "platform_unavailable"
    TIME_ENTRY_IMPOSSIBLE = "time_entry_impossible"
    LOGIN_IMPOSSIBLE = "login_impossible"
    SLOWDOWN = "slowdown"
    FEATURE_UNAVAILABLE = "feature_unavailable"
    PLANNED_MAINTENANCE = "planned_maintenance"


# Single source of truth: each type declares its category and the nature shown
# to controllers (completeness covered by test_every_type_derives_category_and_nature).
TYPE_INCIDENT = {
    TechnicalIncidentType.SERVER_DOWN: (
        TechnicalIncidentCategory.INFRASTRUCTURE,
        TechnicalIncidentNature.PLATFORM_UNAVAILABLE,
    ),
    TechnicalIncidentType.DNS_SWITCH: (
        TechnicalIncidentCategory.INFRASTRUCTURE,
        TechnicalIncidentNature.PLATFORM_UNAVAILABLE,
    ),
    TechnicalIncidentType.SSL_EXPIRED: (
        TechnicalIncidentCategory.INFRASTRUCTURE,
        TechnicalIncidentNature.LOGIN_IMPOSSIBLE,
    ),
    TechnicalIncidentType.DATABASE_DOWN: (
        TechnicalIncidentCategory.INFRASTRUCTURE,
        TechnicalIncidentNature.TIME_ENTRY_IMPOSSIBLE,
    ),
    TechnicalIncidentType.BACKEND_API_UNAVAILABLE: (
        TechnicalIncidentCategory.INFRASTRUCTURE,
        TechnicalIncidentNature.FEATURE_UNAVAILABLE,
    ),
    TechnicalIncidentType.SLOWDOWN_TIMEOUT: (
        TechnicalIncidentCategory.APPLICATIVE,
        TechnicalIncidentNature.SLOWDOWN,
    ),
    TechnicalIncidentType.DEPLOY_REGRESSION: (
        TechnicalIncidentCategory.APPLICATIVE,
        TechnicalIncidentNature.FEATURE_UNAVAILABLE,
    ),
    TechnicalIncidentType.TIME_ENTRY_BUG: (
        TechnicalIncidentCategory.APPLICATIVE,
        TechnicalIncidentNature.TIME_ENTRY_IMPOSSIBLE,
    ),
    TechnicalIncidentType.OFFLINE_SYNC_BUG: (
        TechnicalIncidentCategory.APPLICATIVE,
        TechnicalIncidentNature.TIME_ENTRY_IMPOSSIBLE,
    ),
    TechnicalIncidentType.AUTH_OUTAGE: (
        TechnicalIncidentCategory.ACCESS_EXTERNAL,
        TechnicalIncidentNature.LOGIN_IMPOSSIBLE,
    ),
    TechnicalIncidentType.EMAIL_UNAVAILABLE: (
        TechnicalIncidentCategory.ACCESS_EXTERNAL,
        TechnicalIncidentNature.FEATURE_UNAVAILABLE,
    ),
    TechnicalIncidentType.THIRD_PARTY_OUTAGE: (
        TechnicalIncidentCategory.ACCESS_EXTERNAL,
        TechnicalIncidentNature.FEATURE_UNAVAILABLE,
    ),
    TechnicalIncidentType.PLANNED_MAINTENANCE: (
        TechnicalIncidentCategory.SPECIAL_CASE,
        TechnicalIncidentNature.PLANNED_MAINTENANCE,
    ),
}


class TechnicalIncident(BaseModel):
    __tablename__ = "technical_incident"

    technical_type = enum_column(TechnicalIncidentType, nullable=False)

    start_time = db.Column(DateTimeStoredAsUTC, nullable=False, index=True)
    end_time = db.Column(DateTimeStoredAsUTC, nullable=True)

    description = db.Column(db.Text, nullable=True)

    @property
    def category(self):
        return TYPE_INCIDENT[TechnicalIncidentType(self.technical_type)][0]

    @property
    def nature(self):
        return TYPE_INCIDENT[TechnicalIncidentType(self.technical_type)][1]

    @property
    def is_ongoing(self):
        return (
            self.end_time is None
            and datetime.utcnow() < self.effective_end_time
        )

    @property
    def effective_end_time(self):
        # Real end if set, otherwise the start capped by the visible window.
        if self.end_time is not None:
            return self.end_time
        return self.start_time + ONGOING_INCIDENT_MAX_VISIBLE_DURATION
