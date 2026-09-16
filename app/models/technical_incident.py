from datetime import datetime, timedelta
from enum import Enum

from app import db
from app.helpers.db import DateTimeStoredAsUTC
from app.models.base import BaseModel
from app.models.utils import enum_column

# An ongoing incident (no end date) has its effective end auto-capped to this
# duration, so it stays in the registry without lingering as "down" forever.
ONGOING_INCIDENT_MAX_DURATION = timedelta(hours=24)


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


CATEGORY_BY_TYPE = {
    TechnicalIncidentType.SERVER_DOWN: TechnicalIncidentCategory.INFRASTRUCTURE,
    TechnicalIncidentType.DNS_SWITCH: TechnicalIncidentCategory.INFRASTRUCTURE,
    TechnicalIncidentType.SSL_EXPIRED: TechnicalIncidentCategory.INFRASTRUCTURE,
    TechnicalIncidentType.DATABASE_DOWN: TechnicalIncidentCategory.INFRASTRUCTURE,
    TechnicalIncidentType.BACKEND_API_UNAVAILABLE: TechnicalIncidentCategory.INFRASTRUCTURE,
    TechnicalIncidentType.SLOWDOWN_TIMEOUT: TechnicalIncidentCategory.APPLICATIVE,
    TechnicalIncidentType.DEPLOY_REGRESSION: TechnicalIncidentCategory.APPLICATIVE,
    TechnicalIncidentType.TIME_ENTRY_BUG: TechnicalIncidentCategory.APPLICATIVE,
    TechnicalIncidentType.OFFLINE_SYNC_BUG: TechnicalIncidentCategory.APPLICATIVE,
    TechnicalIncidentType.AUTH_OUTAGE: TechnicalIncidentCategory.ACCESS_EXTERNAL,
    TechnicalIncidentType.EMAIL_UNAVAILABLE: TechnicalIncidentCategory.ACCESS_EXTERNAL,
    TechnicalIncidentType.THIRD_PARTY_OUTAGE: TechnicalIncidentCategory.ACCESS_EXTERNAL,
    TechnicalIncidentType.PLANNED_MAINTENANCE: TechnicalIncidentCategory.SPECIAL_CASE,
}

NATURE_BY_TYPE = {
    TechnicalIncidentType.SERVER_DOWN: TechnicalIncidentNature.PLATFORM_UNAVAILABLE,
    TechnicalIncidentType.DNS_SWITCH: TechnicalIncidentNature.PLATFORM_UNAVAILABLE,
    TechnicalIncidentType.SSL_EXPIRED: TechnicalIncidentNature.LOGIN_IMPOSSIBLE,
    TechnicalIncidentType.AUTH_OUTAGE: TechnicalIncidentNature.LOGIN_IMPOSSIBLE,
    TechnicalIncidentType.DATABASE_DOWN: TechnicalIncidentNature.TIME_ENTRY_IMPOSSIBLE,
    TechnicalIncidentType.TIME_ENTRY_BUG: TechnicalIncidentNature.TIME_ENTRY_IMPOSSIBLE,
    TechnicalIncidentType.OFFLINE_SYNC_BUG: TechnicalIncidentNature.TIME_ENTRY_IMPOSSIBLE,
    TechnicalIncidentType.SLOWDOWN_TIMEOUT: TechnicalIncidentNature.SLOWDOWN,
    TechnicalIncidentType.BACKEND_API_UNAVAILABLE: TechnicalIncidentNature.FEATURE_UNAVAILABLE,
    TechnicalIncidentType.DEPLOY_REGRESSION: TechnicalIncidentNature.FEATURE_UNAVAILABLE,
    TechnicalIncidentType.EMAIL_UNAVAILABLE: TechnicalIncidentNature.FEATURE_UNAVAILABLE,
    TechnicalIncidentType.THIRD_PARTY_OUTAGE: TechnicalIncidentNature.FEATURE_UNAVAILABLE,
    TechnicalIncidentType.PLANNED_MAINTENANCE: TechnicalIncidentNature.PLANNED_MAINTENANCE,
}


class TechnicalIncident(BaseModel):
    __tablename__ = "technical_incident"

    technical_type = enum_column(TechnicalIncidentType, nullable=False)

    start_time = db.Column(DateTimeStoredAsUTC, nullable=False, index=True)
    end_time = db.Column(DateTimeStoredAsUTC, nullable=True)

    description = db.Column(db.Text, nullable=True)

    @property
    def category(self):
        return CATEGORY_BY_TYPE[TechnicalIncidentType(self.technical_type)]

    @property
    def nature(self):
        return NATURE_BY_TYPE[TechnicalIncidentType(self.technical_type)]

    @property
    def is_ongoing(self):
        return self.end_time is None

    @property
    def has_forced_end(self):
        # Ongoing incident kept in the registry but whose end has been
        # auto-capped after the max duration (not manually closed yet).
        return (
            self.is_ongoing
            and datetime.utcnow() - self.start_time
            > ONGOING_INCIDENT_MAX_DURATION
        )

    @property
    def effective_end_time(self):
        # Real end if set, else an ongoing incident is capped at start + max
        # duration so it stays attached without lingering indefinitely.
        if self.end_time is not None:
            return self.end_time
        return min(
            datetime.utcnow(),
            self.start_time + ONGOING_INCIDENT_MAX_DURATION,
        )

    def overlaps_date_range(self, start_date, end_date):
        return (
            self.start_time.date() <= end_date
            and self.effective_end_time.date() >= start_date
        )
