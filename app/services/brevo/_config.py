"""Configuration for Brevo data finders."""

from datetime import date


class BrevoFunnelConfig:
    # Acquisition thresholds
    NEW_COMPANIES_SINCE_DATE = date(2025, 3, 1)
    NO_INVITE_WARNING_DAYS = 7
    NO_INVITE_CRITICAL_DAYS = 30

    # Activation thresholds
    LOW_INVITATION_THRESHOLD = 30
    HIGH_INVITATION_THRESHOLD = 80
    COMPLETE_INVITATION_THRESHOLD = 100
