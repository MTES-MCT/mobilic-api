from flask import jsonify
from cachetools import cached, TTLCache

from app import app
from app.helpers.livestorm import livestorm, NoLivestormCredentialsError

ttl_cache = TTLCache(maxsize=1, ttl=3600)


@app.route("/next-webinars", methods=["GET"])
@cached(cache=ttl_cache)
def get_webinars_list():
    if not app.config["LIVESTORM_API_TOKEN"]:
        raise NoLivestormCredentialsError()
    webinars = sorted(livestorm.get_next_webinars(), key=lambda w: w.time)
    return jsonify([w._asdict() for w in webinars]), 200
