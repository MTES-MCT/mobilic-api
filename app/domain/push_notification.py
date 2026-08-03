import json
import logging

from pywebpush import webpush, WebPushException

from app import app, db
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


def send_push_notification(user_id, title, body, data=None):
    subscriptions = PushSubscription.query.filter_by(user_id=user_id).all()

    if not subscriptions:
        logger.info(f"No push subscription for user {user_id}")
        return

    vapid_private_key = app.config.get("VAPID_PRIVATE_KEY")
    vapid_claim_email = app.config.get("VAPID_CLAIM_EMAIL")

    if not vapid_private_key or not vapid_claim_email:
        logger.warning(
            "VAPID not fully configured, skipping push"
        )
        return

    payload = json.dumps({"title": title, "body": body, "data": data or {}})

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
        except WebPushException as e:
            status = e.response.status_code if e.response else None
            if status in (404, 410):
                logger.info(
                    "Subscription expired for user "
                    "%s, removing",
                    user_id,
                )
                db.session.delete(subscription)
                db.session.commit()
            else:
                logger.error(f"Push failed for user {user_id}: {e}")
