import requests
from datetime import datetime
from typing import Optional

from app import app
from config import MOBILIC_ENV


def send_mattermost_message(thread_title, main_title, main_value, items):
    mattermost_webhook = app.config["MATTERMOST_WEBHOOK"]

    if not mattermost_webhook:
        app.logger.warning("No mattermost webhook configured")
        return

    requests.post(
        mattermost_webhook,
        json={
            "channel": app.config["MATTERMOST_MAIN_CHANNEL"],
            "username": f"{thread_title} - {MOBILIC_ENV.capitalize()}",
            "icon_emoji": ":robot:",
            "attachments": [
                {
                    "title": main_title,
                    "text": main_value,
                    "fields": items,
                }
            ],
        },
    )


def _format_duration(duration_seconds: Optional[float]) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        duration_seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "1.5s", "2m 30s", "N/A")
    """
    if duration_seconds is None:
        return "N/A"

    if duration_seconds < 60:
        return f"{duration_seconds:.1f}s"
    else:
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        return f"{minutes}m {seconds}s"


def _send_brevo_notification(
    username: str, title: str, status_text: str, items: list
) -> None:
    """Send Brevo notification to Mattermost.

    Args:
        username: Username for the notification
        title: Main title of the notification
        status_text: Status text with timestamp
        items: List of fields to display
    """
    mattermost_webhook = app.config.get("MATTERMOST_WEBHOOK")

    if not mattermost_webhook:
        app.logger.warning("No mattermost webhook configured")
        return

    requests.post(
        mattermost_webhook,
        json={
            "channel": app.config["BREVO_ALERTS_CHANNEL"],
            "username": f"{username} - {MOBILIC_ENV.capitalize()}",
            "icon_emoji": ":robot:",
            "attachments": [
                {
                    "title": title,
                    "text": f"{status_text} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "fields": items,
                }
            ],
        },
    )


def send_brevo_deals_linking_notification(
    total_linked: int,
    total_errors: int,
    acquisition_linked: int = 0,
    acquisition_errors: int = 0,
    activation_linked: int = 0,
    activation_errors: int = 0,
    duration_seconds: Optional[float] = None,
    acquisition_pipeline: str = "Acquisition",
    activation_pipeline: str = "Activation",
):
    """Send Mattermost notification for Brevo deals linking completion.

    Args:
        total_linked: Total number of deals linked
        total_errors: Total number of errors
        acquisition_linked: Deals linked in acquisition pipeline
        acquisition_errors: Errors in acquisition pipeline
        activation_linked: Deals linked in activation pipeline
        activation_errors: Errors in activation pipeline
        duration_seconds: Time taken for linking operation
        acquisition_pipeline: Name of acquisition pipeline
        activation_pipeline: Name of activation pipeline
    """

    has_errors = total_errors > 0
    has_success = total_linked > 0

    if not has_success and has_errors:
        status_emoji = "❌"
        status_text = "ECHEC - Aucun deal lié"
    elif has_success and has_errors:
        status_emoji = "⚠️"
        status_text = "SUCCES PARTIEL - Erreurs rencontrées"
    elif has_success and not has_errors:
        status_emoji = "✅"
        status_text = "SUCCES - Tous les deals traités"
    else:
        status_emoji = "ℹ️"
        status_text = "TERMINE - Aucun deal à lier"

    items = [
        {"title": "Deals liés", "value": total_linked, "short": True},
        {
            "title": "Durée d'exécution",
            "value": _format_duration(duration_seconds),
            "short": True,
        },
        {"title": "Erreurs totales", "value": total_errors, "short": True},
        {
            "title": "Deals traités",
            "value": total_linked + total_errors,
            "short": True,
        },
        {
            "title": f"Pipeline {acquisition_pipeline}",
            "value": f"{acquisition_linked} liés, {acquisition_errors} erreurs",
            "short": True,
        },
        {
            "title": f"Pipeline {activation_pipeline}",
            "value": f"{activation_linked} liés, {activation_errors} erreurs",
            "short": True,
        },
    ]

    _send_brevo_notification(
        username="Liaison Deals Brevo CRM",
        title=f"{status_emoji} Liaison des deals Brevo terminée",
        status_text=status_text,
        items=items,
    )


def send_brevo_sync_notification(
    sync_result,
    duration_seconds: Optional[float] = None,
    acquisition_pipeline: str = "Acquisition",
    activation_pipeline: str = "Activation",
):
    """Send Mattermost notification for Brevo sync completion.

    Args:
        sync_result: SyncResult object with sync statistics
        duration_seconds: Time taken for sync operation
        acquisition_pipeline: Name of acquisition pipeline
        activation_pipeline: Name of activation pipeline
    """
    has_errors = len(sync_result.errors) > 0
    is_partial_success = sync_result.total_companies > 0 and has_errors

    if has_errors and sync_result.total_companies == 0:
        status_emoji = "❌"
        status_text = "ECHEC - Aucune entreprise traitée"
    elif is_partial_success:
        status_emoji = "⚠️"
        status_text = "SUCCES PARTIEL - Erreurs rencontrées"
    else:
        status_emoji = "✅"
        status_text = "SUCCES - Toutes les entreprises traitées"

    items = [
        {
            "title": "Entreprises traitées",
            "value": sync_result.total_companies,
            "short": True,
        },
        {
            "title": "Durée d'exécution",
            "value": _format_duration(duration_seconds),
            "short": True,
        },
        {
            "title": "Deals créés",
            "value": sync_result.created_deals,
            "short": True,
        },
        {
            "title": "Deals mis à jour",
            "value": sync_result.updated_deals,
            "short": True,
        },
        {
            "title": f"Pipeline {acquisition_pipeline}",
            "value": sync_result.acquisition_synced,
            "short": True,
        },
        {
            "title": f"Pipeline {activation_pipeline}",
            "value": sync_result.activation_synced,
            "short": True,
        },
    ]

    if has_errors:
        if len(sync_result.errors) <= 3:
            error_details = "; ".join(sync_result.errors)
        else:
            error_details = (
                "; ".join(sync_result.errors[:3])
                + f" (et {len(sync_result.errors) - 3} autres erreurs)"
            )

        items.append(
            {
                "title": "Erreurs rencontrées",
                "value": error_details,
                "short": False,
            }
        )

    _send_brevo_notification(
        username="Synchronisation Brevo CRM",
        title=f"{status_emoji} Synchronisation Brevo CRM terminée",
        status_text=status_text,
        items=items,
    )
