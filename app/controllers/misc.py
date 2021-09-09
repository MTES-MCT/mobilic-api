from flask import jsonify

from app import app
from app.helpers.livestorm import livestorm, NoLivestormCredentialsError


@app.route("/next-webinars", methods=["GET"])
def get_webinars_list():
    if not app.config["LIVESTORM_API_TOKEN"]:
        raise NoLivestormCredentialsError()
    webinars = sorted(livestorm.get_next_webinars(), key=lambda w: w.time)
    return jsonify([w._asdict() for w in webinars]), 200
