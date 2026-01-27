"""Configuration for Brevo data finders."""

from datetime import date


class BrevoFunnelConfig:
    # Acquisition V2
    ACCOUNT_ACTIVATION_DEADLINE_DAYS = 14

    # TODO: Enable after email reminder system implementation
    # Ticket: https://trello.com/c/2Q0k0kzu/2174
    # ACCOUNT_ACTIVATION_REMINDER_DAYS = 2
    # REMINDER_EMAIL_TYPE = "company_no_activation_reminder"

    # Activation thresholds
    LOW_INVITATION_THRESHOLD = 30
    HIGH_INVITATION_THRESHOLD = 80
    COMPLETE_INVITATION_THRESHOLD = 100

    # Activation pipeline (days since company creation)
    ACTIVATION_EMAIL_J7_DAYS = 7
    ACTIVATION_PHONING_J10_DAYS = 10
    ACTIVATION_EMAIL_J14_DAYS = 14
    ACTIVATION_DEADLINE_DAYS = 21
