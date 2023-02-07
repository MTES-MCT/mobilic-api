from functools import wraps

from argon2 import PasswordHasher
from flask import request

from app import app
from app.helpers.authentication import CLIENT_ID_HTTP_HEADER_NAME
from app.helpers.errors import AuthenticationError
from app.helpers.oauth.models import ThirdPartyClientCompany

API_KEY_HTTP_HEADER_NAME = "X-API-KEY"


def request_client_id():
    try:
        return request.headers.get(CLIENT_ID_HTTP_HEADER_NAME)
    except Exception as e:
        return None


def require_api_key_decorator(func):
    @wraps(func)
    def inner(*args, **kwargs):
        if not check_api_key():
            raise AuthenticationError("Invalid API Key")
        return func(*args, **kwargs)

    return inner


def check_api_key():
    from app.helpers.oauth.models import ThirdPartyApiKey

    api_key_parameter = request.headers.get(API_KEY_HTTP_HEADER_NAME)
    client_id = request.headers.get(CLIENT_ID_HTTP_HEADER_NAME)
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
            try:
                if ph.verify(db_api_key.api_key, api_key):
                    return True
            except Exception as e:
                continue
    return False


def check_protected_client_id(client_id):
    return str(client_id) == str(request_client_id())


def check_protected_client_id_company_id(company_id):
    client_company_link = ThirdPartyClientCompany.query.filter(
        ThirdPartyClientCompany.client_id == request_client_id(),
        ThirdPartyClientCompany.company_id == company_id,
        ~ThirdPartyClientCompany.is_dismissed,
    ).one_or_none()
    return client_company_link is not None
