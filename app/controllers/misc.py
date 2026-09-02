import json
import logging

from flask import jsonify

from app import app
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
