from flask import request, abort
from functools import wraps


def service_decorator(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        from app import app

        token = request.form.get("token")
        if token and token == app.config["MOBILIC_SERVICE_ACTOR_TOKEN"]:
            return f(*args, **kwargs)
        abort(403 if token else 401)

    return wrapper
