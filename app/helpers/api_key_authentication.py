from functools import wraps

import graphene
from argon2 import PasswordHasher
from flask import request

from app import app
from app.helpers.errors import AuthenticationError


def require_api_key_decorator(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if not check_api_key():
            raise AuthenticationError("Invalid API Key")
        return func(*args, **kwargs)

    return inner


def check_api_key():
    from app.helpers.oauth.models import ThirdPartyApiKey

    api_key_parameter = request.headers.get("X-API-KEY")
    client_id = request.headers.get("X-CLIENT_ID")
    if not api_key_parameter or not client_id:
        return False
    api_key_prefix = api_key_parameter[0 : len(app.config["API_KEY_PREFIX"])]
    api_key = api_key_parameter[len(app.config["API_KEY_PREFIX"]) :]
    if (
        api_key_prefix == app.config["API_KEY_PREFIX"]
        and api_key
        and client_id
    ):
        ph = PasswordHasher()
        db_api_keys = ThirdPartyApiKey.query.filter(
            ThirdPartyApiKey.client_id == client_id
        ).all()
        for db_api_key in db_api_keys:
            if ph.verify(db_api_key.api_key, api_key):
                return True
    raise False


class ProtectedMutation(graphene.Mutation, abstract=True):
    @classmethod
    def __init_subclass__(cls, **kwargs):
        cls.mutate = require_api_key_decorator(cls.mutate)
        super(ProtectedMutation, cls).__init_subclass__(**kwargs)


def check_protected_client_id(client_id):
    request_client_id = request.headers.get("X-CLIENT_ID")
    return str(client_id) == str(request_client_id)
