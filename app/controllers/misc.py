import json
import logging

import redis as redis_module
from flask import jsonify

from app import app
from app.helpers.livestorm import livestorm, NoLivestormCredentialsError

logger = logging.getLogger(__name__)

WEBINARS_CACHE_KEY = "livestorm:next_webinars"
WEBINARS_CACHE_TTL = 3600

_redis_client = None


def _get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_module.Redis.from_url(
            app.config["CELERY_BROKER_URL"],
            socket_connect_timeout=3,
            socket_timeout=3,
        )
    return _redis_client


@app.route("/next-webinars", methods=["GET"])
def get_webinars_list():
    if not app.config["LIVESTORM_API_TOKEN"]:
        raise NoLivestormCredentialsError()

    try:
        cached = _get_redis_client().get(WEBINARS_CACHE_KEY)
        if cached:
            return jsonify(json.loads(cached)), 200
    except Exception:
        logger.warning("Redis unavailable, skipping cache read for webinars")

    webinars = sorted(livestorm.get_next_webinars(), key=lambda w: w.time)
    webinars_data = [w._asdict() for w in webinars]

    try:
        _get_redis_client().setex(
            WEBINARS_CACHE_KEY, WEBINARS_CACHE_TTL, json.dumps(webinars_data)
        )
    except Exception:
        logger.warning("Redis unavailable, skipping cache write for webinars")

    return jsonify(webinars_data), 200
