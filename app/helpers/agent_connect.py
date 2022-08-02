import json
import urllib.request

import jwt
import requests
from jwt import PyJWKClient

from app import app
from app.helpers.errors import AgentConnectAuthenticationError


def get_agent_connect_user_info(authorization_code, original_redirect_uri):
    data = {
        "code": authorization_code,
        "grant_type": "authorization_code",
        "client_id": app.config["AC_CLIENT_ID"],
        "client_secret": app.config["AC_CLIENT_SECRET"],
        "redirect_uri": original_redirect_uri,
    }

    token_response = requests.post(f"{app.config['AC_TOKEN_URL']}", data=data)

    if token_response.status_code != 200:
        raise AgentConnectAuthenticationError(
            "Unable to get a token from the authorization code"
        )

    token_response_json = token_response.json()
    id_token = token_response_json["id_token"]

    user_info_response = requests.get(
        f"{app.config['AC_USER_INFO_URL']}",
        headers={
            "Authorization": "Bearer " + token_response.json()["access_token"]
        },
    )

    if user_info_response.status_code != 200:
        raise AgentConnectAuthenticationError(
            "Unable to get user info from token"
        )

    jwt_token_response = user_info_response.content.decode("utf-8")

    jwks_client = PyJWKClient(app.config["AC_JWKS_INFO"])
    signing_key = jwks_client.get_signing_key_from_jwt(jwt_token_response)

    try:
        user_info = jwt.decode(
            jwt_token_response,
            signing_key.key,
            algorithms=["ES256"],
            audience=app.config["AC_AUDIENCE"],
        )
    except json.decoder.JSONDecodeError:
        raise AgentConnectAuthenticationError("Unable to parse user info")

    return user_info, id_token
