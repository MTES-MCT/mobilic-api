import hmac
import json
import logging

import redis as redis_module
from flask import jsonify, request

from app import app, db
from app.helpers.livestorm import livestorm, NoLivestormCredentialsError
from app.helpers.redis import get_redis_client

logger = logging.getLogger(__name__)

WEBINARS_CACHE_KEY = "livestorm:next_webinars"
WEBINARS_CACHE_TTL = 60 * 60 * 6


def refresh_webinars_cache():
    """Fetch upcoming Livestorm webinars and store them in Redis.

    Called by the cron, off the web request path, so a slow or rate-limited
    Livestorm can never block a web worker.
    """
    if not app.config["LIVESTORM_API_TOKEN"]:
        return
    webinars = sorted(livestorm.get_next_webinars(), key=lambda w: w.time)
    webinars_data = [w._asdict() for w in webinars]
    get_redis_client().setex(
        WEBINARS_CACHE_KEY, WEBINARS_CACHE_TTL, json.dumps(webinars_data)
    )


@app.route("/vapid-public-key", methods=["GET"])
def get_vapid_public_key():
    public_key = app.config.get("VAPID_PUBLIC_KEY")
    if not public_key:
        return jsonify({"error": "VAPID not configured"}), 503

    from app.models.push_banner_config import PushBannerConfig

    config = PushBannerConfig.get_current()
    result = {"publicKey": public_key}
    if config:
        result["bannerText"] = config.banner_text
    return jsonify(result), 200


@app.route("/next-webinars", methods=["GET"])
def get_webinars_list():
    if not app.config["LIVESTORM_API_TOKEN"]:
        raise NoLivestormCredentialsError()

    try:
        cached = get_redis_client().get(WEBINARS_CACHE_KEY)
        if cached:
            return jsonify(json.loads(cached)), 200
    except Exception:
        logger.warning("Redis unavailable, skipping cache read for webinars")

    return jsonify([]), 200


@app.route("/campaign-click", methods=["GET"])
@app.route("/api/campaign-click", methods=["GET"])
def campaign_click():
    campaign_id = request.args.get("c")
    token = request.args.get("t")
    if not campaign_id or not token:
        return "", 400

    try:
        campaign_id = int(campaign_id)
    except (ValueError, TypeError):
        return "", 400

    from app.jobs.notification_campaign import (
        generate_click_token,
    )

    expected = generate_click_token(campaign_id)
    if not hmac.compare_digest(token, expected):
        return "", 403

    from app.models.notification_campaign import (
        NotificationCampaign,
    )

    db.session.query(NotificationCampaign).filter(
        NotificationCampaign.id == campaign_id
    ).update(
        {
            NotificationCampaign.clicked_count: (
                NotificationCampaign.clicked_count + 1
            )
        },
        synchronize_session=False,
    )
    db.session.commit()

    return "", 204
