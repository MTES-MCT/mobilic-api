"""
Performance monitoring middleware for detecting slow queries and requests.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
from flask import g, request

from app import app
from app.helpers.mattermost import send_mattermost_message

logger = logging.getLogger(__name__)


@dataclass
class PerformanceThresholds:
    """Configuration for performance thresholds."""

    CRITICAL_MS: int = 5000  # 5 seconds
    WARNING_MS: int = 2000  # 2 seconds
    INFO_MS: int = 1000  # 1 second

    # Specific thresholds for different operations
    GRAPHQL_QUERY_MS: int = 3000
    GRAPHQL_MUTATION_MS: int = 2000
    REST_API_MS: int = 1000
    EXPORT_MS: int = 10000  # Exports can be slower


@dataclass
class SlowRequestAlert:
    """Data structure for slow request alerts."""

    endpoint: str
    method: str
    duration_ms: int
    status_code: int
    user_id: Optional[int]
    user_email: Optional[str]
    graphql_operation: Optional[str]
    variables: Optional[Dict[str, Any]]
    timestamp: datetime
    severity: str  # 'critical', 'warning', 'info'
    client_id: Optional[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/alerting."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def format_mattermost_message(self) -> str:
        """Format alert for Mattermost notification."""
        emoji = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}[self.severity]

        message = f"{emoji} **Requête lente détectée**\n"
        message += f"- **Durée**: {self.duration_ms}ms\n"
        message += f"- **Endpoint**: `{self.method} {self.endpoint}`\n"

        if self.graphql_operation:
            message += f"- **Opération GraphQL**: `{self.graphql_operation}`\n"

        if self.user_email:
            message += (
                f"- **Utilisateur**: {self.user_email} (ID: {self.user_id})\n"
            )

        message += f"- **Status**: {self.status_code}\n"
        message += f"- **Client**: {self.client_id or 'Unknown'}\n"

        if self.variables and self.severity == "critical":
            # Only show variables for critical alerts
            vars_str = json.dumps(self.variables, indent=2)[:500]  # Limit size
            message += f"```json\n{vars_str}\n```\n"

        return message


class PerformanceMonitor:
    """Main performance monitoring class."""

    def __init__(self, thresholds: Optional[PerformanceThresholds] = None):
        self.thresholds = thresholds or PerformanceThresholds()
        self.enabled = app.config.get("PERFORMANCE_MONITORING_ENABLED", True)
        self.alert_channel = app.config.get(
            "PERFORMANCE_ALERT_CHANNEL", "mobilic-perf"
        )

    def analyze_request(
        self, duration_ms: int, response_status: int
    ) -> Optional[SlowRequestAlert]:
        """Analyze a request and create alert if needed."""
        if not self.enabled or not hasattr(g, "log_info"):
            return None

        # Determine threshold based on operation type
        threshold = self._get_threshold_for_request()

        if duration_ms < threshold["info"]:
            return None

        # Determine severity
        if duration_ms >= threshold["critical"]:
            severity = "critical"
        elif duration_ms >= threshold["warning"]:
            severity = "warning"
        else:
            severity = "info"

        # Get user info from context
        from app.helpers.authentication import current_user

        user_id = current_user.id if current_user else None
        user_email = current_user.email if current_user else None

        # Create alert
        alert = SlowRequestAlert(
            endpoint=request.path,
            method=request.method,
            duration_ms=duration_ms,
            status_code=response_status,
            user_id=user_id,
            user_email=user_email,
            graphql_operation=g.log_info.get("graphql_op_short"),
            variables=self._sanitize_variables(g.log_info.get("vars")),
            timestamp=datetime.utcnow(),
            severity=severity,
            client_id=g.log_info.get("client_id"),
        )

        return alert

    def _get_threshold_for_request(self) -> Dict[str, int]:
        """Get appropriate thresholds based on request type."""
        path = request.path

        # Check if it's an export
        if "export" in path.lower() or "download" in path.lower():
            return {
                "info": self.thresholds.EXPORT_MS // 2,
                "warning": self.thresholds.EXPORT_MS * 3 // 4,
                "critical": self.thresholds.EXPORT_MS,
            }

        # Check if it's GraphQL
        if "/graphql" in path:
            if hasattr(g, "log_info") and g.log_info.get("graphql_op_short"):
                op = g.log_info["graphql_op_short"].lower()
                if "mutation" in op:
                    base = self.thresholds.GRAPHQL_MUTATION_MS
                else:
                    base = self.thresholds.GRAPHQL_QUERY_MS
            else:
                base = self.thresholds.GRAPHQL_QUERY_MS

            return {
                "info": base // 2,
                "warning": base * 3 // 4,
                "critical": base,
            }

        # Default REST API
        return {
            "info": self.thresholds.INFO_MS,
            "warning": self.thresholds.WARNING_MS,
            "critical": self.thresholds.CRITICAL_MS,
        }

    def _sanitize_variables(self, variables: Any) -> Optional[Dict[str, Any]]:
        """Remove sensitive data from variables."""
        if not variables or not isinstance(variables, dict):
            return None

        sensitive_keys = [
            "password",
            "token",
            "secret",
            "api_key",
            "access_token",
            "refresh_token",
        ]

        def sanitize_dict(d: dict) -> dict:
            result = {}
            for key, value in d.items():
                if any(s in key.lower() for s in sensitive_keys):
                    result[key] = "***REDACTED***"
                elif isinstance(value, dict):
                    result[key] = sanitize_dict(value)
                elif (
                    isinstance(value, list)
                    and value
                    and isinstance(value[0], dict)
                ):
                    result[key] = [
                        sanitize_dict(item) if isinstance(item, dict) else item
                        for item in value[:3]
                    ]  # Limit arrays
                else:
                    result[key] = value
            return result

        return sanitize_dict(variables)

    def handle_alert(self, alert: SlowRequestAlert):
        """Handle a performance alert."""
        # Always log
        logger.warning(
            f"Slow request detected: {alert.duration_ms}ms for {alert.method} {alert.endpoint}",
            extra=alert.to_dict(),
        )

        # Send to Mattermost for warning and critical
        if alert.severity in ["warning", "critical"]:
            try:
                send_mattermost_message(
                    alert.format_mattermost_message(),
                    channel=self.alert_channel,
                )
            except Exception as e:
                logger.error(f"Failed to send Mattermost alert: {e}")

        # Store in database for analysis (future enhancement)
        # self._store_performance_metric(alert)


# Global instance
performance_monitor = PerformanceMonitor()


def check_request_performance(duration_ms: int, response_status: int):
    """
    Check if request performance is acceptable and create alerts if needed.
    Called from the logging middleware.
    """
    try:
        alert = performance_monitor.analyze_request(
            duration_ms, response_status
        )
        if alert:
            performance_monitor.handle_alert(alert)
    except Exception as e:
        logger.error(f"Error in performance monitoring: {e}")
