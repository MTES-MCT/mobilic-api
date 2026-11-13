import base64
import hashlib
import hmac
import json
import logging

import redis as redis_module
from flask import g, jsonify, request

from app import app, db
from app.helpers.brevo import brevo
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


@app.route("/global-banner", methods=["GET"])
def get_global_banner():
    from app.models.global_banner_config import GlobalBannerConfig

    config = GlobalBannerConfig.get_current()
    if not config or not config.enabled:
        return jsonify({"enabled": False}), 200
    return (
        jsonify(
            {
                "enabled": True,
                "message": config.message,
                "level": config.level.value,
            }
        ),
        200,
    )


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


def _tally_field_text(field):
    value = field.get("value")
    if isinstance(value, list):
        by_id = {
            o.get("id"): o.get("text") for o in field.get("options") or []
        }
        return ", ".join(str(by_id.get(v, v)) for v in value)
    return value


def parse_tally_csat(payload):
    """Map a Tally C-SAT webhook payload to (email, Brevo attributes).

    Questions are matched by field type plus a keyword in the label, so the
    mapping survives a label reword. The respondent email comes from an email
    question or a hidden field filled by the Brevo link.
    """
    data = (payload or {}).get("data") or {}
    email = None
    attributes = {}
    for field in data.get("fields") or []:
        field_type = (field.get("type") or "").upper()
        label = (field.get("label") or "").lower()
        value = field.get("value")
        if value in (None, "", []):
            continue
        if field_type == "INPUT_EMAIL" or "email" in label:
            if isinstance(value, str):
                email = value
        elif field_type in ("RATING", "LINEAR_SCALE"):
            if "satisf" in label:
                attributes["CSAT_SUPPORT_SATISFACTION"] = value
            elif "quali" in label or "accompagn" in label:
                attributes["CSAT_SUPPORT_QUALITY"] = value
        elif field_type in ("MULTIPLE_CHOICE", "DROPDOWN", "CHECKBOXES"):
            if "résol" in label or "resol" in label:
                attributes["CSAT_SUPPORT_RESOLVED"] = _tally_field_text(field)
        elif field_type in ("TEXTAREA", "INPUT_TEXT"):
            attributes["CSAT_SUPPORT_COMMENT"] = value

    created_at = data.get("createdAt") or (payload or {}).get("createdAt")
    if isinstance(created_at, str) and created_at:
        attributes["CSAT_SUPPORT_DATE"] = created_at[:10]
    return email, attributes


@app.route("/webhooks/tally-csat", methods=["POST"])
def tally_csat_webhook():
    # RGPD: keep the respondent email and free-text comment out of access logs.
    if hasattr(g, "log_info"):
        g.log_info["vars"] = "[redacted: tally-csat]"

    secret = app.config.get("TALLY_WEBHOOK_SECRET")
    if not secret:
        logger.error("TALLY_WEBHOOK_SECRET not configured")
        return "", 503

    expected = base64.b64encode(
        hmac.new(secret.encode(), request.get_data(), hashlib.sha256).digest()
    ).decode()
    if not hmac.compare_digest(
        request.headers.get("Tally-Signature", ""), expected
    ):
        return "", 403

    payload = request.get_json(silent=True) or {}
    email, attributes = parse_tally_csat(payload)
    if not email or "CSAT_SUPPORT_SATISFACTION" not in attributes:
        field_types = [
            field.get("type")
            for field in (payload.get("data") or {}).get("fields") or []
        ]
        logger.error(
            "Tally C-SAT webhook: incomplete payload "
            "(email_present=%s, score_present=%s, field_types=%s)",
            bool(email),
            "CSAT_SUPPORT_SATISFACTION" in attributes,
            field_types,
        )
        return "", 422

    brevo.upsert_contact_attributes(email, attributes)
    return "", 204


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
