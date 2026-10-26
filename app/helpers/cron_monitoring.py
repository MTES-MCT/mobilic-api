"""Sentry Crons instrumentation for the scheduled flask commands.

Each entry maps a command scheduled in cron.json to its Sentry monitor
config. ``schedule`` mirrors the crontab in cron.json (kept in sync by
test_cron_monitoring); ``max_runtime`` and ``checkin_margin`` (minutes)
are operational knobs tuned to each cron's cadence and dyno size.

Commands chained after another with ``&&`` in cron.json do not start at
their crontab time but once the predecessor finishes, so their
``checkin_margin`` is widened to absorb the predecessor's ``max_runtime``
and avoid a nightly false "missed check-in".
"""

from sentry_sdk.crons import monitor

CRON_MONITORS = {
    "run_certificate": {
        "schedule": {"type": "crontab", "value": "0 4 1 * *"},
        "max_runtime": 180,
        "checkin_margin": 60,
    },
    "send_daily_emails": {
        "schedule": {"type": "crontab", "value": "0 3 * * *"},
        "max_runtime": 30,
        "checkin_margin": 30,
    },
    "delete_old_notifications": {
        "schedule": {"type": "crontab", "value": "0 4 * * *"},
        "max_runtime": 30,
        "checkin_margin": 30,
    },
    "load_company_stats": {
        "schedule": {"type": "crontab", "value": "0 5 * * *"},
        "max_runtime": 30,
        "checkin_margin": 30,
    },
    "purge_support_action_logs": {
        "schedule": {"type": "crontab", "value": "0 5 * * *"},
        "max_runtime": 30,
        "checkin_margin": 30,
    },
    "sync_brevo_funnel": {
        "schedule": {"type": "crontab", "value": "0 2 * * *"},
        "max_runtime": 60,
        "checkin_margin": 30,
    },
    "link_brevo_deals": {
        "schedule": {"type": "crontab", "value": "30 2 * * *"},
        "max_runtime": 60,
        "checkin_margin": 30,
    },
    "update_ceased_activity_status": {
        "schedule": {"type": "crontab", "value": "30 1 * * *"},
        "max_runtime": 30,
        "checkin_margin": 30,
    },
    "process_auto_validations": {
        "schedule": {"type": "crontab", "value": "0 * * * *"},
        "max_runtime": 15,
        "checkin_margin": 10,
    },
    # chained after process_auto_validations (max_runtime 15)
    "refresh_webinars_cache": {
        "schedule": {"type": "crontab", "value": "0 * * * *"},
        "max_runtime": 15,
        "checkin_margin": 20,
    },
    "anonymize_users": {
        "schedule": {"type": "crontab", "value": "30 3 * * *"},
        "max_runtime": 120,
        "checkin_margin": 30,
    },
    # chained after anonymize_users (max_runtime 120)
    "migrate_anonymize_data": {
        "schedule": {"type": "crontab", "value": "30 3 * * *"},
        "max_runtime": 120,
        "checkin_margin": 150,
    },
    "compute_software_compliance_snapshot": {
        "schedule": {"type": "crontab", "value": "30 3 * * *"},
        "max_runtime": 30,
        "checkin_margin": 30,
    },
    "delete_expired_refresh_tokens": {
        "schedule": {"type": "crontab", "value": "45 4 * * *"},
        "max_runtime": 30,
        "checkin_margin": 30,
    },
    "purge_downloaded_exports": {
        "schedule": {"type": "crontab", "value": "0 * * * *"},
        "max_runtime": 15,
        "checkin_margin": 10,
    },
    # chained after purge_downloaded_exports (max_runtime 15)
    "alert_stuck_exports": {
        "schedule": {"type": "crontab", "value": "0 * * * *"},
        "max_runtime": 15,
        "checkin_margin": 20,
    },
}

_DEFAULT_TIMEZONE = "Etc/UTC"


def cron_monitor(command_name):
    config = {"timezone": _DEFAULT_TIMEZONE, **CRON_MONITORS[command_name]}
    sentry_decorator = monitor(
        monitor_slug=command_name.replace("_", "-"), monitor_config=config
    )

    def decorator(func):
        wrapped = sentry_decorator(func)
        wrapped.__cron_monitor_command__ = command_name
        return wrapped

    return decorator
