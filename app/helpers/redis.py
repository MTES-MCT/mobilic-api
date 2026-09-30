import redis as redis_module
from redis.backoff import NoBackoff
from redis.retry import Retry

from app import app

_redis_client = None


def get_redis_client():
    # 3s timeouts so Redis outages never block a web worker; callers must
    # catch exceptions and fall back to their uncached path.
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_module.Redis.from_url(
            app.config["CELERY_BROKER_URL"],
            socket_connect_timeout=3,
            socket_timeout=3,
            retry=Retry(NoBackoff(), 0),
        )
    return _redis_client
