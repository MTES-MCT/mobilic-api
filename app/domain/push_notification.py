import json
import logging

from pywebpush import webpush, WebPushException

from app import app, db
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


def send_push_notification(
    user_id, title, body, data=None, subscriptions=None
):
    """Returns True if at least one push was sent successfully."""
    if subscriptions is None:
        subscriptions = PushSubscription.query.filter_by(
            user_id=user_id
        ).all()

    if not subscriptions:
        logger.info(f"No push subscription for user {user_id}")
        return False

    vapid_private_key = app.config.get("VAPID_PRIVATE_KEY")
    vapid_claim_email = app.config.get("VAPID_CLAIM_EMAIL")

    if not vapid_private_key or not vapid_claim_email:
        logger.warning(
            "VAPID not fully configured, skipping push"
        )
        return False

    payload = json.dumps({"title": title, "body": body, "data": data or {}})
    success = False
    expired = []

    for subscription in subscriptions:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh_key,
                "auth": subscription.auth_key,
            },
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": vapid_claim_email},
            )
            success = True
        except WebPushException as e:
            status = e.response.status_code if e.response else None
            if status in (404, 410):
                logger.info(
                    "Subscription expired for user "
                    "%s, removing",
                    user_id,
                )
                expired.append(subscription)
            else:
                logger.exception(f"Push failed for user {user_id}")

    if expired:
        for sub in expired:
            db.session.delete(sub)
        db.session.commit()

    return success
